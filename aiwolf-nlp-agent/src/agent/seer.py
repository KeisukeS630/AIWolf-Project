"""Module that defines the Seer agent class.

占い師のエージェントクラスを定義するモジュール.
"""

from __future__ import annotations

from typing import Any

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
        """Initialize the seer agent.

        占い師のエージェントを初期化する.

        Args:
            config (dict[str, Any]): Configuration dictionary / 設定辞書
            name (str): Agent name / エージェント名
            game_id (str): Game ID / ゲームID
            role (Role): Role (ignored, always set to SEER) / 役職(無視され、常にSEERに設定)
        """
        super().__init__(config, name, game_id, Role.SEER)
        self.has_co: bool = False  # すでにCO(カミングアウト)したかどうかを覚えておくフラグ
        self.my_divination_results: dict[int, Judge] = {} # 日付と、その日の占い結果を保存する辞書
        self.werewolves: list[str] = [] # 占いによって人狼だと判明したエージェントのリスト

    def talk(self) -> str:
        """Return response to talk request.

        トークリクエストに対する応答を返す.

        Returns:
            str: Talk message / 発言メッセージ
        """
        # 1日目、かつ、まだCOしていない場合
        if self.info.day == 1 and not self.has_co:
            self.has_co = True  # COしたことを記憶する
            co_text = f"COMINGOUT {self.agent_name} SEER"
            self.agent_logger.logger.info(f"Day 1なのでCOします: {co_text}")
            return co_text
        
        # それ以外の日は、ひとまず親クラスのランダム発言に任せる
        return super().talk()

    def divine(self) -> str:
        """Return response to divine request.

        占いリクエストに対する応答を返す.

        Returns:
            str: Agent name to divine / 占い対象のエージェント名
        """
        #
        return super().divine()

    def vote(self) -> str:
        """Return response to vote request.

        投票リクエストに対する応答を返す.

        Returns:
            str: Agent name to vote / 投票対象のエージェント名
        """
        return super().vote()
