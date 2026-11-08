"""Synthetic acceptance catalogue. It is not a bulk/provisioning API for real schools."""

import uuid
from typing import Any, TypedDict


class FixtureSpec(TypedDict):
    role: str
    school: str | None


def identifier(name: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, "retiro-e1-synthetic/" + name))


def catalogue() -> dict[str, FixtureSpec]:
    users: dict[str, FixtureSpec] = {}
    for school in ["a", "b"]:
        for family in ["1", "2"]:
            for kind in ["p", "s"]:
                users[f"e1-{school}-{kind}{family}"] = {"role": "PADRE", "school": school}
        users[f"e1-{school}-guard"] = {"role": "GUARDIA", "school": school}
        users[f"e1-{school}-admin"] = {"role": "ADMIN_ESCUELA", "school": school}
    users["e1-system"] = {"role": "ADMIN_SISTEMA", "school": None}
    return users


def roster_payload(issuer: str, users: dict[str, Any]) -> dict[str, Any]:
    if set(users) != set(catalogue()):
        raise ValueError("Complete synthetic catalogue required")
    result: dict[str, Any] = {
        "schema_version": 1,
        "synthetic_only": True,
        "schools": [],
        "sites": [],
        "accounts": [],
        "parents": [],
        "students": [],
        "links": [],
    }
    for name, entry in catalogue().items():
        sub = str(uuid.UUID(users[name]["sub"]))
        role, school = entry["role"], entry["school"]
        account = {
            "id": identifier(name),
            "issuer": issuer,
            "subject": sub,
            "role": role,
            "school_id": identifier(f"school-{school}")
            if role in {"GUARDIA", "ADMIN_ESCUELA"}
            else None,
            "site_id": identifier(f"site-{school}") if role == "GUARDIA" else None,
        }
        result["accounts"].append(account)
        if role == "PADRE":
            result["parents"].append(
                {"id": identifier("parent-" + name), "account_id": account["id"]}
            )
    for school in ["a", "b"]:
        sid, site = identifier("school-" + school), identifier("site-" + school)
        result["schools"].append({"id": sid, "name": f"Escuela sintética E1 {school.upper()}"})
        result["sites"].append(
            {"id": site, "school_id": sid, "name": "Sede sintética", "timezone": "America/Bogota"}
        )
        for child, family in [("1", "1"), ("2", "1"), ("3", "2")]:
            student = identifier(f"student-{school}-{child}")
            result["students"].append(
                {
                    "id": student,
                    "school_id": sid,
                    "site_id": site,
                    "display_name": f"Estudiante sintético {school.upper()}{child}",
                }
            )
            for kind in ["p", "s"]:
                name = f"e1-{school}-{kind}{family}"
                result["links"].append(
                    {
                        "id": identifier(f"link-{school}-{child}-{kind}"),
                        "school_id": sid,
                        "student_id": student,
                        "parent_id": identifier("parent-" + name),
                        "principal": kind == "p",
                    }
                )
    return result
