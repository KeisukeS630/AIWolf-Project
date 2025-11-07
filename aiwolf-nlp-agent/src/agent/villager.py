"""Module that defines the Villager agent class.

村人のエージェントクラスを定義するモジュール.
"""

from __future__ import annotations

from typing import Any

from aiwolf_nlp_common.packet import Role

from agent.agent import Agent

import random


class Villager(Agent):
    """Villager agent class.

    村人のエージェントクラス.
    """

    def __init__(
        self,
        config: dict[str, Any],
        name: str,
        game_id: str,
        role: Role,  # noqa: ARG002
    ) -> None:
        """Initialize the villager agent.

        村人のエージェントを初期化する.

        Args:
            config (dict[str, Any]): Configuration dictionary / 設定辞書
            name (str): Agent name / エージェント名
            game_id (str): Game ID / ゲームID
            role (Role): Role (ignored, always set to VILLAGER) / 役職(無視され、常にVILLAGERに設定)
        """
        super().__init__(config, name, game_id, Role.VILLAGER)

    def talk(self) -> str:
        """Return response to talk request.

        トークリクエストに対する応答を返す.

        Returns:
            str: Talk message / 発言メッセージ
        """
        return super().talk()

    def vote(self) -> str:
        """Return response to vote request. (Villager version)

        投票リクエストに対する応答を返す（村人バージョン）.
        占い師の黒出しを信頼し、白出しを回避する。

        Returns:
            str: Agent name to vote / 投票対象のエージェント名
        """
        # --- 1. 意思決定の前に、最新の情報を解析する ---251107
        # (agent.py の vote() をオーバーライドするので、忘れずに呼ぶ)
        self._update_game_state()

        # --- 2. 情報を整理 ---
        alive_agents = self.get_alive_agents()
        my_name = self.info.agent
        
        # 黒判定された生存者 (自分を除く)
        # (agent.py から self.divined_as_black を参照)
        black_list = {
            agent for agent in self.divined_as_black 
            if agent in alive_agents and agent != my_name
        }
        
        # 白判定された生存者 (自分を除く)
        # (agent.py から self.divined_as_white を参照)
        white_list = {
            agent for agent in self.divined_as_white
            if agent in alive_agents and agent != my_name
        }

        # --- 3. 投票ロジック ---
        
        # [優先度1] 黒判定された生存者がいれば、その人に投票
        if black_list:
            # set から list に変換して random.choice を使う
            target = random.choice(list(black_list)) # type: ignore
            self.agent_logger.logger.info(f"黒判定リスト {black_list} から {target} に投票します。")
            return target

        # [優先度2] 黒判定の人がいない場合、グレーの人（白判定されておらず、自分でもない）に投票
        gray_list = [
            agent for agent in alive_agents 
            if agent != my_name and agent not in white_list
        ]
        
        if gray_list:
            target = random.choice(gray_list) # type: ignore
            self.agent_logger.logger.info(f"グレーリスト {gray_list} (白でも黒でもない) から {target} に投票します。")
            return target
            
        # [優先度3] グレーの人もいない場合（自分以外の全員が白だった場合など）
        # 自分以外の生存者にランダム投票 (agent.py のロジック)
        fallback_candidates = [agent for agent in alive_agents if agent != my_name]
        if fallback_candidates:
            target = random.choice(fallback_candidates) # type: ignore
            self.agent_logger.logger.info(f"黒もグレーもいないため、自分以外の生存者 {fallback_candidates} から {target} に投票します。")
            return target

        # [優先度4] (万が一) 自分しかいない場合は自分に投票
        self.agent_logger.logger.warning("投票候補が自分しかいません。")
        return my_name
