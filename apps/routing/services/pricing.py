"""
Margin / markup rules: turning our cost into a customer sell rate.

Rule priority (most specific wins):
  customer + prefix  >  customer + country  >  customer default
  >  global prefix   >  global country      >  global default
Within prefix rules the longest matching prefix wins.
"""
from decimal import ROUND_CEILING, Decimal

from ..models import MarginRule

DEFAULT_PERCENT = Decimal("10")


def specificity(rule, prefix, country_id):
    """Score a rule for a destination, or None if it does not apply."""
    score = 1000 if rule.customer_id else 0
    if rule.prefix:
        if not prefix.startswith(rule.prefix):
            return None
        return score + 200 + len(rule.prefix)
    if rule.country_id:
        if rule.country_id != country_id:
            return None
        return score + 100
    return score


class MarginResolver:
    def __init__(self, customer):
        self.customer = customer
        self.rules = list(
            MarginRule.objects.filter(is_active=True)
            .filter(customer__isnull=True) | MarginRule.objects.filter(is_active=True, customer=customer)
        )

    def rule_for(self, prefix, country_id):
        best, best_score = None, -1
        for rule in self.rules:
            score = specificity(rule, prefix, country_id)
            if score is not None and score > best_score:
                best, best_score = rule, score
        return best

    def sell_rate(self, cost, rule):
        """Apply the rule, enforce the minimum margin, then round UP so we never sell below cost."""
        cost = Decimal(cost)
        if rule is None:
            sell = cost * (1 + DEFAULT_PERCENT / 100)
            min_margin = Decimal("0")
        elif rule.kind == MarginRule.Kind.PERCENT:
            sell = cost * (1 + rule.value / 100)
            min_margin = rule.min_margin
        else:
            sell = cost + rule.value
            min_margin = rule.min_margin
        if sell - cost < min_margin:
            sell = cost + min_margin
        step = Decimal(1).scaleb(-self.customer.rate_decimals)
        return sell.quantize(step, rounding=ROUND_CEILING)
