import random
from typing import Dict, Optional

from negmas import MechanismState
from negmas import ResponseType
from negmas import SAOResponse
from negmas import SAOState, Outcome
from negmas import SAOSingleAgreementRandomController, SAOSingleAgreementController

from scml.oneshot.agent import (
    OneShotAgent,
    OneShotSingleAgreementAgent,
    OneShotSyncAgent,
)
from scml.oneshot.agent import OneShotSyncAgent
from scml.scml2020.common import QUANTITY, TIME, UNIT_PRICE

__all__ = ["GreedyOneShotAgent", "GreedySyncAgent", "GreedySingleAgreementAgent"]


class GreedyOneShotAgent(OneShotAgent):
    """A greedy agent based on `OneShotAgent`"""

    def init(self):
        self._sales = self._supplies = 0

    def step(self):
        self._sales = self._supplies = 0

    def on_negotiation_success(self, contract, mechanism):
        if contract.annotation["seller"] == self.id:
            self._sales += contract.agreement["quantity"]
        else:
            self._supplies += contract.agreement["quantity"]

    def propose(self, negotiator_id: str, state) -> "Outcome":
        return self.best_offer(negotiator_id)

    def respond(self, negotiator_id, state, offer):
        my_needs = self._needed(negotiator_id)
        if my_needs <= 0:
            return ResponseType.END_NEGOTIATION
        if state.step == self.negotiators[negotiator_id][0].ami.n_steps - 1:
            return (
                ResponseType.ACCEPT_OFFER
                if offer[QUANTITY] <= my_needs
                else ResponseType.REJECT_OFFER
            )
        return ResponseType.REJECT_OFFER

    def best_offer(self, negotiator_id):
        my_needs = self._needed(negotiator_id)
        if my_needs <= 0:
            return None
        quantity_issue = self.negotiators[negotiator_id][0].ami.issues[QUANTITY]
        unit_price_issue = self.negotiators[negotiator_id][0].ami.issues[UNIT_PRICE]
        offer = [-1] * 3
        offer[QUANTITY] = max(
            min(my_needs, quantity_issue.max_value), quantity_issue.min_value
        )
        offer[TIME] = self.awi.current_step
        if self._is_selling(negotiator_id):
            offer[UNIT_PRICE] = unit_price_issue.max_value
        else:
            offer[UNIT_PRICE] = unit_price_issue.min_value
        return tuple(offer)

    def _needed(self, negotiator_id):
        summary = self.awi.exogenous_contract_summary
        secured = self._sales if self._is_selling(negotiator_id) else self._supplies
        return min(summary[0][0], summary[-1][0]) - secured

    def _is_selling(self, negotiator_id):
        return self.negotiators[negotiator_id][0].ami.annotation["seller"] == self.id


class GreedySyncAgent(OneShotSyncAgent, GreedyOneShotAgent):
    """Greedy agent based on `OneShotSyncAgent`"""

    def first_proposals(self):
        """Decide a first proposal on every negotiation.
        Returning None for a negotiation means ending it."""
        return dict(
            zip(
                self.negotiators.keys(),
                (self.best_offer(_) for _ in self.negotiators.keys()),
            )
        )

    def counter_all(self, offers, states):
        """Respond to a set of offers given the negotiation state of each."""
        responses = {
            k: SAOResponse(ResponseType.REJECT_OFFER, _)
            for k, v in self.first_proposals().items()
        }
        my_needs = self._needed(None)
        sorted_offers = sorted(
            zip(offers.values(), (self._is_selling(_) for _ in offers.keys())),
            key=lambda x: (-x[0][UNIT_PRICE]) if x[1] else x[0][UNIT_PRICE],
        )
        secured, outputs, chosen = 0, [], dict()
        for i, k in enumerate(offers.keys()):
            offer, is_output = sorted_offers[i]
            secured += offer[QUANTITY]
            if secured >= my_needs:
                break
            chosen[k] = offer
            outputs.append(is_output)

        u = self.ufun.from_offers(list(chosen.values()), outputs)
        if u > 0.7 * self.ufun.max_utility:
            for k, v in chosen.items():
                responses[k] = SAOResponse(ResponseType.ACCEPT_OFFER, None)
        return responses


class GreedySingleAgreementAgent(OneShotSingleAgreementAgent):
    """ A greedy agent based on `OneShotSingleAgreementAgent`"""

    def init(self):
        self.__endall = self.awi.is_middle_level

    def is_acceptable(self, offer, source, state) -> bool:
        if self.__endall:
            return False
        return self.ufun(offer) > 0.7 * self.ufun.max_utility

    def best_offer(self, offers):
        ufuns = [(self.ufun(_), i) for i, _ in enumerate(offers.values())]
        keys = list(offers.keys())
        return keys[max(ufuns)[1]]

    def is_better(self, a, b, negotiator, state):
        return self.ufun(a) > self.ufun(b)
