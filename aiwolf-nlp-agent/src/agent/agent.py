"""Module that defines the base class for agents.

エージェントの基底クラスを定義するモジュール.
"""

from __future__ import annotations

import random
from pathlib import Path
from typing import TYPE_CHECKING, Any, ParamSpec, TypeVar

from aiwolf_nlp_common.packet import Info, Packet, Request, Role, Setting, Status, Talk, Species

from utils.agent_logger import AgentLogger
from utils.stoppable_thread import StoppableThread

if TYPE_CHECKING:
    from collections.abc import Callable

P = ParamSpec("P")
T = TypeVar("T")


class Agent:
    """Base class for agents.

    エージェントの基底クラス.
    """

    def __init__(
        self,
        config: dict[str, Any],
        name: str,
        game_id: str,
        role: Role,
    ) -> None:
        """Initialize the agent.

        エージェントの初期化を行う.

        Args:
            config (dict[str, Any]): Configuration dictionary / 設定辞書
            name (str): Agent name / エージェント名
            game_id (str): Game ID / ゲームID
            role (Role): Role / 役職
        """
        self.config = config
        self.agent_name = name
        self.agent_logger = AgentLogger(config, name, game_id)
        self.request: Request | None = None
        self.info: Info | None = None
        self.setting: Setting | None = None
        self.talk_history: list[Talk] = []
        self.whisper_history: list[Talk] = []
        self.role = role

        # ▼▼▼ 以下のブロックを差し替え ▼▼▼251107
        
        self.comments: list[str] = []
        # configからファイルパスを取得
        file_path_str = str(self.config["path"]["random_talk"])
        file_path = Path(file_path_str)

        try:
            # pathlib を使ってファイルを開く
            with file_path.open(encoding="utf-8") as f:
                content = f.read()
                self.comments = content.splitlines()

            # 読み込み結果をログに出力
            if not self.comments:
                # ファイルは存在したが、中身が空だった場合
                self.agent_logger.logger.warning(f"__init__: ランダム発話ファイルは見つかりましたが、中身が空です: {file_path_str}")
            else:
                # 成功
                self.agent_logger.logger.info(f"__init__: {len(self.comments)}行のランダム発話を読み込みました。 (例: {self.comments[0]})")

        except FileNotFoundError:
            # ファイル自体が見つからなかった場合
            self.agent_logger.logger.error(f"__init__: ランダム発話ファイルが見つかりません！")
            self.agent_logger.logger.error(f"__init__: 実行パス: {Path.cwd()}")
            self.agent_logger.logger.error(f"__init__: 探したパス: {file_path.absolute()}")
        except Exception as e:
            # その他のエラー（パーミッションなど）
            self.agent_logger.logger.error(f"__init__: ランダム発話ファイルの読み込み中に予期せぬエラー: {e}")
        
        # ▲▲▲ 差し替えここまで ▲▲▲

        # --- ★追加★ 戦略のためのゲーム状態変数 ---251107
        
        # 議論のターン（何番目の発言まで読んだか）
        self.talk_turn: int = 0
        
        # 投票宣言 {発言者: 投票先} (毎日リセット)
        self.vote_declarations: dict[str, str] = {}
        
        # --- 永続的な情報（CO、占い結果）---
        # これらは daily_initialize でリセット *しない*
        
        # ★要求1: COした占い師のリスト (Setで重複なし)
        self.seer_co_agents: set[str] = set()
        
        # ★要求2: 占われて黒だった人のリスト (Setで重複なし)
        self.divined_as_black: set[str] = set()

        # ★要求3: 占われて白だった人のリスト (Setで重複なし)
        self.divined_as_white: set[str] = set()
        
        # (参考) より詳細な占い・霊媒の結果報告リスト (報告者, 対象, 役職)
        self.divined_reports: list[tuple[str, str, Role | Species]] = []

    @staticmethod
    def timeout(func: Callable[P, T]) -> Callable[P, T]:
        """Decorator to set action timeout.

        アクションタイムアウトを設定するデコレータ.

        Args:
            func (Callable[P, T]): Function to be decorated / デコレート対象の関数

        Returns:
            Callable[P, T]: Function with timeout functionality / タイムアウト機能を追加した関数
        """

        def _wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            res: T | Exception = Exception("No result")

            def execute_with_timeout() -> None:
                nonlocal res
                try:
                    res = func(*args, **kwargs)
                except Exception as e:  # noqa: BLE001
                    res = e

            thread = StoppableThread(target=execute_with_timeout)
            thread.start()
            self = args[0] if args else None
            if not isinstance(self, Agent):
                raise TypeError(self, " is not an Agent instance")
            timeout_value = (self.setting.timeout.action if hasattr(self, "setting") and self.setting else 0) // 1000
            if timeout_value > 0:
                thread.join(timeout=timeout_value)
                if thread.is_alive():
                    self.agent_logger.logger.warning(
                        "アクションがタイムアウトしました: %s",
                        self.request,
                    )
                    if bool(self.config["agent"]["kill_on_timeout"]):
                        thread.stop()
                        self.agent_logger.logger.warning(
                            "アクションを強制終了しました: %s",
                            self.request,
                        )
            else:
                thread.join()
            if isinstance(res, Exception):  # type: ignore[arg-type]
                raise res
            return res

        return _wrapper

    def set_packet(self, packet: Packet) -> None:
        """Set packet information.

        パケット情報をセットする.

        Args:
            packet (Packet): Received packet / 受信したパケット
        """
        self.request = packet.request
        if packet.info:
            self.info = packet.info
        if packet.setting:
            self.setting = packet.setting
        if packet.talk_history:
            self.talk_history.extend(packet.talk_history)
        if packet.whisper_history:
            self.whisper_history.extend(packet.whisper_history)
        if self.request == Request.INITIALIZE:
            self.talk_history: list[Talk] = []
            self.whisper_history: list[Talk] = []
        self.agent_logger.logger.debug(packet)

    def get_alive_agents(self) -> list[str]:
        """Get the list of alive agents.

        生存しているエージェントのリストを取得する.

        Returns:
            list[str]: List of alive agent names / 生存エージェント名のリスト
        """
        if not self.info:
            return []
        return [k for k, v in self.info.status_map.items() if v == Status.ALIVE]

    def name(self) -> str:
        """Return response to name request.

        名前リクエストに対する応答を返す.

        Returns:
            str: Agent name / エージェント名
        """
        return self.agent_name

    def initialize(self) -> None:
        """Perform initialization for game start request.

        ゲーム開始リクエストに対する初期化処理を行う.
        """

    def daily_initialize(self) -> None:
        """Perform processing for daily initialization request.

        昼開始リクエスト (毎朝)。
        毎日の揮発性情報(発言ターン、投票先宣言)をリセットし、
        議論開始前にゲーム状態(昨晩の占い結果など)を更新する。
        """
        # 毎朝リセットする情報251107
        self.talk_turn = 0
        self.vote_declarations = {}
        
        # 毎朝リセット *しない* 情報 (CO、占い結果)251107
        # self.seer_co_agents 
        # self.divined_as_black
        # self.divined_as_white
        
        self.agent_logger.logger.info(f"{self.info.day}日目の朝になりました。")
        
        # 議論開始前に、昨晩の結果や、(あれば)0日目のCOなどを解析251107
        self._update_game_state()


    # --- ★追加★ 議論解析用のヘルパー関数 ---251107

    def _update_game_state(self) -> None:
        """発言履歴(talk_history)を解析し、ゲーム状態を更新する (全役職共通)."""
        
        # まだ読んでいない発言 (self.talk_turn 以降) をチェック
        new_talks = self.talk_history[self.talk_turn:]
        
        for talk in new_talks:
            # 自分の発言は解析しない (無限ループ防止)
            if talk.agent == self.info.agent:
                continue
            
            text = talk.text
            parts = text.split() # テキストを単語に分割

            # try-except で囲み、予期せぬ形式 (例: 空の発言) でもクラッシュしないようにする
            try:
                # 0番目の単語（発言タイプ）が存在しない場合はスキップ
                if not parts:
                    continue

                command = parts[0] # "VOTE", "DIVINED", "COMINGOUT" など

                # (1) 占い師CO: "COMINGOUT Agent[01] SEER" (※Agent[01]は発言者自身)
                # Note: COMINGOUT の発言者は talk.agent_name
                # "ミヅキ" が "COMINGOUT ミヅキ SEER" と言った場合、
                # talk.agent_name は "ミヅキ"
                if command == "COMINGOUT" and len(parts) >= 3 and parts[-1] == "SEER":
                    # ▼▼▼ 修正箇所 ▼▼▼
                    # ログ出力する前にリストに追加
                    self.seer_co_agents.add(talk.agent) 
                    # リストの内容もログに出力
                    self.agent_logger.logger.info(f"解析: {talk.agent} が SEER CO を記録。現在リスト: {self.seer_co_agents}")
                    # ▲▲▲ 修正箇所 ▲▲▲
                
                # (2) 占い結果: "DIVINED セルヴァス WEREWOLF" or "DIVINED セルヴァス HUMAN"
                elif command == "DIVINED" and len(parts) == 3:
                    target = parts[1] # "セルヴァス"
                    result_str = parts[2] # "WEREWOLF" or "HUMAN"
                    
                    if result_str == "WEREWOLF":
                        result_role = Role.WEREWOLF
                        # ▼▼▼ 修正箇所 ▼▼▼
                        self.divined_as_black.add(target)
                        self.agent_logger.logger.info(f"解析: {target} が黒判定 (発言者: {talk.agent})。現在リスト: {self.divined_as_black}")
                        # ▲▲▲ 修正箇所 ▲▲▲
                    elif result_str == "HUMAN":
                        result_role = Species.HUMAN
                        # ▼▼▼ 修正箇所 ▼▼▼
                        self.divined_as_white.add(target)
                        self.agent_logger.logger.info(f"解析: {target} が白判定 (発言者: {talk.agent})。現在リスト: {self.divined_as_white}")
                        # ▲▲▲ 修正箇所 ▲▲▲
                    else:
                        continue # 不明な結果
                    
                    # 詳細リストに追加
                    self.divined_reports.append((talk.agent, target, result_role))

                # (3) 投票宣言: "VOTE セルヴァス"
                elif command == "VOTE" and len(parts) == 2:
                    target = parts[1] # "セルヴァス"
                    # ▼▼▼ 修正箇所 ▼▼▼
                    self.vote_declarations[talk.agent] = target
                    self.agent_logger.logger.info(f"解析: {talk.agent} が {target} へ投票宣言。現在リスト: {self.vote_declarations}")
                    # ▲▲▲ 修正箇所 ▲▲▲

                # (将来的に: 霊媒CO、霊媒結果などの解析もここに追加)

            except IndexError:
                # parts[1] などが存在しない場合 (不正な形式) は無視
                self.agent_logger.logger.debug(f"解析不能な発言: {text}")
            except Exception as e:
                self.agent_logger.logger.warning(f"発言解析中に予期せぬエラー: {e} (Text: {text})")

        # 既読位置を更新
        self.talk_turn = len(self.talk_history)

    def whisper(self) -> str:
        """Return response to whisper request.

        囁きリクエストに対する応答を返す.

        Returns:
            str: Whisper message / 囁きメッセージ
        """
        # ★注意: 人狼は _update_game_state ではなく、
        # _update_whisper_state のような専用のものを将来的に作る必要がある
        return random.choice(self.comments)  # noqa: S311

    def talk(self) -> str:
        """Return response to talk request.

        トークリクエストに対する応答を返す.

        Returns:
            str: Talk message / 発言メッセージ
        """
        # --- ★追加★ 発言する前に、最新の情報を解析する ---251107
        self._update_game_state()
        
        # ▼▼▼ 推敲（Day 0 挨拶の復活）▼▼▼251107
        # self.info が None でないことを確認し、0日目かどうかを判定
        if self.info and self.info.day == 0:
            # 0日目なら挨拶を返す (self.agent_name ではなく self.info.agent を使う)
            return f"こんにちは！ {self.info.agent} です。よろしくお願いします。"
        # ▲▲▲ 推敲 ▲▲▲

        # ▼▼▼ 推敲（random.choice の安全化）▼▼▼251107
        # 1日目以降: self.comments が空でないか確認
        if self.comments:
            return random.choice(self.comments)  # noqa: S311
        
        # ▼▼▼ 修正箇所（デバッグログの強化） ▼▼▼
        # self.comments が空の場合のフォールバック
        self.agent_logger.logger.warning("talk(): self.comments が空です！")
        
        # __init__ で失敗した可能性のあるパス情報を、ここで出力する
        try:
            file_path_str = str(self.config["path"]["random_talk"])
            file_path = Path(file_path_str)
            self.agent_logger.logger.error(f"talk(): ランダム発話ファイルが見つからないようです。")
            self.agent_logger.logger.error(f"talk(): 実行パス: {Path.cwd()}")
            self.agent_logger.logger.error(f"talk(): configで探したパス: {file_path_str}")
            self.agent_logger.logger.error(f"talk(): 絶対パス: {file_path.absolute()}")
        except Exception as e:
            self.agent_logger.error(f"talk(): configのパス指定('path.random_talk')が間違っているようです: {e}")

        return "Over"
        # ▲▲▲ 修正箇所 ▲▲▲

    def daily_finish(self) -> None:
        """Perform processing for daily finish request.

        昼終了リクエストに対する処理を行う.
        """

    def divine(self) -> str:
        """Return response to divine request.

        占いリクエストに対する応答を返す.

        Returns:
            str: Agent name to divine / 占い対象のエージェント名
        """
        return random.choice(self.get_alive_agents())  # noqa: S311

    def guard(self) -> str:
        """Return response to guard request.

        護衛リクエストに対する応答を返す.

        Returns:
            str: Agent name to guard / 護衛対象のエージェント名
        """
        return random.choice(self.get_alive_agents())  # noqa: S311

    def vote(self) -> str:
        """Return response to vote request.

        投票リクエストに対する応答を返す.

        Returns:
            str: Agent name to vote / 投票対象のエージェント名
        """
        # --- ★追加★ 意思決定の前に、最新の情報を解析する ---251107
        self._update_game_state()

        # ▼▼▼ 修正箇所 ▼▼▼
        # 生存者リストを取得
        alive_agents = self.get_alive_agents()

        # 自分以外の生存者リストを作成
        candidates = [agent for agent in alive_agents if agent != self.info.agent]
        
        if candidates:
            # 自分以外の候補がいればランダムに選ぶ
            target = random.choice(candidates) # type: ignore
            self.agent_logger.logger.info(f"自分以外の生存者 {candidates} から {target} に投票します。")
            return target
        
        # もし自分しか生存者がいなければ (安全策)
        self.agent_logger.logger.warning("投票候補が自分しかいません。")
        return self.info.agent
        # ▲▲▲ 修正箇所 ▲▲▲


    def attack(self) -> str:
        """Return response to attack request.

        襲撃リクエストに対する応答を返す.

        Returns:
            str: Agent name to attack / 襲撃対象のエージェント名
        """
        return random.choice(self.get_alive_agents())  # noqa: S311

    def finish(self) -> None:
        """Perform processing for game finish request.

        ゲーム終了リクエストに対する処理を行う.
        """

    @timeout
    def action(self) -> str | None:  # noqa: C901, PLR0911
        """Execute action according to request type.

        リクエストの種類に応じたアクションを実行する.

        Returns:
            str | None: Action result string or None / アクションの結果文字列またはNone
        """
        match self.request:
            case Request.NAME:
                return self.name()
            case Request.TALK:
                return self.talk()
            case Request.WHISPER:
                return self.whisper()
            case Request.VOTE:
                return self.vote()
            case Request.DIVINE:
                return self.divine()
            case Request.GUARD:
                return self.guard()
            case Request.ATTACK:
                return self.attack()
            case Request.INITIALIZE:
                self.initialize()
            case Request.DAILY_INITIALIZE:
                self.daily_initialize()
            case Request.DAILY_FINISH:
                self.daily_finish()
            case Request.FINISH:
                self.finish()
            case _:
                pass
        return None
