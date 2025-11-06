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
        # 1. 1日目、かつ、まだCOしていない場合251030
        if self.info.day == 1 and not self.has_co:
            self.has_co = True  # COしたことを記憶する251030
            co_text = f"私は占い師です。"#--英語が正解？--251106
            self.agent_logger.logger.info(f"Day 1なのでCOします: {co_text}")
            return co_text
        
        # 2. 占い結果の報告処理251106
        # 自分の「記憶」(my_divination_results)をすべてチェック251106
        for day, result in self.my_divination_results.items():
            
            # 「その日の結果(day)」が「報告済みリスト(reported_days)」にまだ入っていないか？251106
            if day not in self.reported_days:
                
                # まだ報告していない新情報なので、報告する251106
                report_text = f"{result.target}を占って{result.result.value}と出ました。"#--英語が正解？--251106
                self.agent_logger.logger.info(f"新しい占い結果を報告します: {report_text}")
                
                # 報告したので、忘れないように「報告済みリスト」に追加する251106
                self.reported_days.append(day)
                
                # 発言を返して、このターンのtalk()処理を終了251106
                return report_text
        
        # 3. デフォルトの発言処理
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
            if agent != self.agent_name and agent not in divined_agents
        ]

        # 候補者がいれば、その中からランダムで選ぶ2511106
        if candidates:
            target = random.choice(candidates) # type: ignore 2511106
            self.agent_logger.logger.info(f"占い候補者 {candidates} の中から {target} を占います。")
            return target
            
        # 候補者がいない場合（全員占ってしまった場合など）は、自分以外の生存者からランダム2511106
        fallback_candidates = [agent for agent in alive_agents if agent != self.agent_name]
        if fallback_candidates:
            return random.choice(fallback_candidates) # type: ignore 2511106
        
        return super().divine()

    def vote(self) -> str:
        return super().vote()
