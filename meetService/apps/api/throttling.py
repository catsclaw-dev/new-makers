from rest_framework.throttling import UserRateThrottle


class SensitiveActionThrottle(UserRateThrottle):
    """Лимит для действий, создающих или меняющих чувствительные сущности."""

    scope = "sensitive_actions"
