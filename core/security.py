"""
Stand-in for real JWT auth (core/security.py in the real Fregix repo).

This demo has no login screen — every request is treated as belonging to
a single fixed demo organization/user, so you can see the module work
end-to-end without wiring up real authentication. Swap this for the real
core/security.py once this merges into the actual app.
"""

DEMO_ORG_ID = 1
DEMO_USER_ID = 1


def get_current_org_id() -> int:
    return DEMO_ORG_ID


def get_current_user_id() -> int:
    return DEMO_USER_ID
