"""P9-B shutdown sequence simulation, no live process control.

Only a supplied fake controller can be invoked and only with
simulate=True. Live execution is deliberately NOT implemented here.
"""
from __future__ import annotations

from installer.rag_p9b_supervised_shutdown_plan import make_shutdown_plan


ORDER = ("GUI", "MCP", "ADAPTER", "TUNNEL")


def rehearse_shutdown_sequence(installed, *, records, controller=None,
                               simulate=False):
    base = {
        "state": "SEQUENCE_REFUSED",
        "simulated": False,
        "real_signals_sent": False,
        "installer_executed": False,
        "deployment_approved": False,
    }
    if simulate is not True or controller is None:
        return {**base, "reason": "SIMULATOR_REQUIRED"}
    plan = make_shutdown_plan(installed, records=records)
    if plan["state"] != "SHUTDOWN_PLAN_ONLY":
        return {**base, "reason": "INVALID_SHUTDOWN_PLAN",
                "plan_state": plan["state"]}
    by_role = {p["component"]: p for p in plan["processes"]}
    trace = []
    for role in ORDER:
        item = by_role[role]
        # The injected controller may only simulate and must be explicitly
        # named as a test double. No production object is permitted.
        if getattr(controller, "simulation_only", False) is not True:
            return {**base, "reason": "NON_SIMULATION_CONTROLLER",
                    "trace": trace}
        accepted = controller.simulate_stop(role, item["pid"],
                                            item["create_time"])
        trace.append({"component": role, "pid": item["pid"],
                      "simulated_accept": accepted is True})
        if accepted is not True:
            return {**base, "state": "SIMULATED_SEQUENCE_ABORTED",
                    "simulated": True, "trace": trace}
    return {**base, "state": "SIMULATED_SEQUENCE_PASS",
            "simulated": True, "trace": trace,
            "identity_digest": plan["identity_digest"]}
