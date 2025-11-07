"""Module that defines the Seer agent class.

占い師のエージェントクラスを定義するモジュール.
"""

from __future__ import annotations

from typing import Any

import random #251106

from aiwolf_nlp_common.packet import Role

from aiwolf_nlp_common.packet import Judge, Species

from agent.agent import Agent


class Seer(Agent):
    """Seer agent class.

    占い師のエージェントクラス.
    """

    def __init__(
        self,
        config: dict[str, Any],
        name: str,
        game_id: str,
        role: Role,  # noqa: ARG002
    ) -> None:
        super().__init__(config, name, game_id, Role.SEER)
        self.has_co: bool = False  # すでにCO(カミングアウト)したかどうかを覚えておくフラグ251030
        self.my_divination_results: dict[int, Judge] = {} # 日付と、その日の占い結果を保存する辞書251030
        self.werewolves: list[str] = [] # 占いによって人狼だと判明したエージェントのリスト251030
        self.reported_days: list[int] = []# 「何日目」の占い結果を報告したかを記憶するリスト。251106

    # --- daily_initializeメソッドをここに追加 ---251106
    def daily_initialize(self) -> None:
        super().daily_initialize()

        # サーバーから占い結果(divine_result)が届いているかチェック251106
        if self.info.divine_result:
            # 届いていれば、その結果(Judgeオブジェクト)を取得251106
            result_judge = self.info.divine_result
            day = result_judge.day
            target = result_judge.target
            result = result_judge.result
            
            # 自分の「記憶用の辞書」に、日付(int)をキーとして結果(Judge)を保存251106
            self.my_divination_results[day] = result_judge
            self.agent_logger.logger.info(f"{day}日目の占い結果を記憶しました: {target} は {result}")

            # もし結果が人狼(WEREWOLF)なら、人狼リストにも追加251106
            if result == Species.WEREWOLF:
                if target not in self.werewolves:
                    self.werewolves.append(target)

    def talk(self) -> str:
        # self.info が None でないか念のため確認 (安全策)251107
        if self.info is None:
            self.agent_logger.logger.warning("self.info が None のため、super().talk() を呼びます。")
            return super().talk()

        # 1. 1日目、かつ、まだCOしていない場合251030
        if self.info.day == 1 and not self.has_co:
            self.has_co = True  # COしたことを記憶する251030
            
            # ▼▼▼ デバッグログ追加 ▼▼▼251107
            # self.info.agent の中身をログに出力する
            agent_name_to_co = self.info.agent
            self.agent_logger.logger.info(f"COに使用する名前: '{agent_name_to_co}' (型: {type(agent_name_to_co)})")
            # ▲▲▲ デバッグログ追加 ▲▲▲

            co_text = f"COMINGOUT {agent_name_to_co} SEER" #--英語が正解？--251106 #英語に修正、自分の名前を言うように修正251107
            self.agent_logger.logger.info(f"Day 1なのでCOします: {co_text}")
            return co_text
        
        # 2. 占い結果の報告処理251106
        for day, result in self.my_divination_results.items():
            if day not in self.reported_days:
                report_text = f"DIVINED {result.target} {result.result.value}" 
                self.agent_logger.logger.info(f"新しい占い結果を報告します: {report_text}")
                self.reported_days.append(day)
                return report_text
        
        # 3. デフォルトの発言処理
        # ▼▼▼ デバッグログ追加 ▼▼▼251107
        self.agent_logger.logger.info("COも占い報告もせず、super().talk() を呼びます。")
        if not self.comments: # self.comments が空かどうかもチェック
             self.agent_logger.logger.warning("self.comments が空です！ random_talk のファイルを確認してください。")
        # ▲▲▲ デバッグログ追加 ▲▲▲
        
        return super().talk()

    def divine(self) -> str:
        # 生存者リストを取得2511106
        alive_agents = self.get_alive_agents()

        # すでに占ったことがあるエージェントのリストを作成2511106
        divined_agents = [result.target for result in self.my_divination_results.values()]

        # 占い候補者のリストを作成2511106
        # (生きている AND 自分ではない AND まだ占っていない)2511106
        candidates = [
            agent for agent in alive_agents 
            
            # ▼▼▼ 修正箇所 1 ▼▼▼
            if agent != self.info.agent and agent not in divined_agents
            # ▲▲▲ 修正箇所 1 ▲▲▲
        ]

        # 候補者がいれば、その中からランダムで選ぶ2511106
        if candidates:
            target = random.choice(candidates) # type: ignore 2511106
            self.agent_logger.logger.info(f"占い候補者 {candidates} の中から {target} を占います。")
            return target
            
        # 候補者がいない場合（全員占ってしまった場合など）は、自分以外の生存者からランダム2511106
        
        # ▼▼▼ 修正箇所 2 ▼▼▼
        fallback_candidates = [agent for agent in alive_agents if agent != self.info.agent]
        # ▲▲▲ 修正箇所 2 ▲▲▲
        
        if fallback_candidates:
            return random.choice(fallback_candidates) # type: ignore 2511106
        
        return super().divine()

    def vote(self) -> str: #251107
        """Return response to vote request.

        投票リクエストに対する応答を返す.

        Returns:
            str: Agent name to vote / 投票対象のエージェント名
        """
        # --- 意思決定の前に、最新の情報を解析する ---
        self._update_game_state()

        # 1. 自分が占って「黒（WEREWOLF）」だったエージェントのリスト
        # ▼▼▼ 修正箇所 (Role -> Species) ▼▼▼
        my_black_list = {
            result.target for result in self.my_divination_results.values() 
            if result.result == Species.WEREWOLF 
        }
        # ▲▲▲ 修正箇所 ▲▲▲
        
        # 2. 他の人が「黒（WEREWOLF）」と報告したエージェントのリスト
        other_black_list = self.divined_as_black

        # 3. 生存者リスト
        alive_agents = self.get_alive_agents()
        my_name = self.info.agent # (self.info.agent が安全)

        # 4. 投票候補者リスト（黒判定された生存者）
        candidates = []
        for agent in alive_agents:
            if agent in my_black_list or agent in other_black_list:
                if agent != my_name:
                    candidates.append(agent)
        
        # 5. 黒判定の人がいれば、その人に投票
        if candidates:
            target = random.choice(candidates) # type: ignore
            self.agent_logger.logger.info(f"黒判定リスト {candidates} から {target} に投票します。")
            return target
        
        # ▼▼▼ 修正箇所 (グレー投票ロジックの追加) ▼▼▼
        # 6. 黒判定の人がいない場合、グレーの人（自分が白出ししていない人）に投票
        
        # 自分が白出しした人のリスト
        my_white_list = {
            result.target for result in self.my_divination_results.values()
            if result.result == Species.HUMAN
        }
        
        # グレーリスト (生存者 AND 自分以外 AND 自分が白出ししていない)
        gray_list = [
            agent for agent in alive_agents
            if agent != my_name and agent not in my_white_list
        ]
        
        if gray_list:
            target = random.choice(gray_list) # type: ignore
            self.agent_logger.logger.info(f"黒判定者がいないため、グレーリスト {gray_list} (自分が白判定していない) から {target} に投票します。")
            return target

        # 7. グレーの人もいない場合（＝自分以外の生存者全員を白判定した場合）
        # 自分以外の生存者からランダムに選ぶ（白判定した人に投票せざるを得ない）
        fallback_candidates = [agent for agent in alive_agents if agent != my_name]
        if fallback_candidates:
            target = random.choice(fallback_candidates) # type: ignore
            self.agent_logger.logger.info(f"黒もグレーもいないため、自分以外の生存者 {fallback_candidates} から {target} に投票します。")
            return target
        # ▲▲▲ 修正箇所 ▲▲▲

        # 8. (万が一) 自分しかいない場合は自分に投票
        self.agent_logger.logger.warning("投票候補が自分しかいません。")
        return my_name