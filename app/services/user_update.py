from fastapi import Request

UPDATABLE_USER_FIELDS = {
    "name",
    "patronymic",
    "surname",
    "company_name",
    "position",
    "about_myself",
    "phone_number",
    "mobile_phone",
    "work_phone",
    "date_of_birth",
    "department",
    "experience",
    "in_organization_since",
    "organization",
    "personnel_number",
    "room",
    "workplace",
    "email",
}


async def parse_update_me_payload(request: Request) -> dict[str, str]:
    content_type = request.headers.get("content-type", "")
    if "application/json" in content_type:
        body = await request.json()
        if not isinstance(body, dict):
            return {}
        return {key: str(value) for key, value in body.items() if value is not None}

    form = await request.form()
    return {key: str(value) for key, value in form.items() if value is not None}
