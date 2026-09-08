"""
Handler registry: maps job_type -> the function that actually does the work.

This is the piece that keeps the Scheduler/Producer "dumb" — they just
say "run generate_weekly_report", they never know what that involves.
Only this registry + the functions it points to know that.
"""

HANDLERS = {}


def register(job_type: str):
    """Decorator to register a function as the handler for a job_type."""
    def decorator(func):
        HANDLERS[job_type] = func
        return func
    return decorator


# --- Example handler for your actual use case ---

@register("generate_weekly_report")
def generate_weekly_report(payload: dict):
    manager_id = payload["manager_id"]
    report_format = payload.get("format", "pdf")

    # TODO: real implementation —
    #   1. query complaints from last 7 days for this manager's hotel
    #   2. render into `report_format`
    #   3. email it to the manager
    print(f"Generating {report_format} report for manager {manager_id}")
    # raise an exception here to simulate/test failure handling