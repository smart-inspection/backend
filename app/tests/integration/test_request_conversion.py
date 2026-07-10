from conftest import log_api_response


api_prefix = "/api/v1"


def create_inspection_request(client):
    response = client.post(
        f"{api_prefix}/inspection-requests",
        json={
            "company_name": "Transportes del Norte S.A.C.",
            "contact_name": "María López",
            "contact_email": "maria.lopez@transportesnorte.com",
            "contact_phone": "999888777",
            "requested_date": "2026-07-15",
            "location": "Trujillo",
            "service_type": "Inspección técnica periódica",
            "equipment_type": "Semirremolque",
            "notes": "Solicitud creada para prueba de conversión.",
        },
    )

    log_api_response(
        "POST",
        f"{api_prefix}/inspection-requests",
        response,
    )

    assert response.status_code == 201, (
        f"Error al crear solicitud de inspección: "
        f"status_code={response.status_code}, "
        f"response={response.text}"
    )

    return response.json()


def create_inspection(client):
    response = client.post(
        f"{api_prefix}/inspections",
        json={
            "code": "INT-REQUEST-001",
            "client_name": "Transportes del Norte S.A.C.",
            "equipment_type": "Semirremolque",
            "inspection_type": "Inspección técnica periódica",
            "inspection_date": "2026-07-20",
            "location": "Trujillo",
            "requested_by": "María López",
            "status": "draft",
        },
    )

    log_api_response(
        "POST",
        f"{api_prefix}/inspections",
        response,
    )

    assert response.status_code == 201, (
        f"Error al crear inspección: "
        f"status_code={response.status_code}, "
        f"response={response.text}"
    )

    return response.json()


def convert_inspection_request(
    client,
    inspection_request_id,
    inspection_id,
):
    response = client.patch(
        f"{api_prefix}/inspection-requests/{inspection_request_id}/convert",
        json={
            "inspection_id": inspection_id,
        },
    )

    log_api_response(
        "PATCH",
        f"{api_prefix}/inspection-requests/{inspection_request_id}/convert",
        response,
    )

    assert response.status_code == 200, (
        f"Error al convertir solicitud de inspección: "
        f"status_code={response.status_code}, "
        f"response={response.text}"
    )

    return response.json()


def get_inspection_request(
    client,
    inspection_request_id,
):
    response = client.get(
        f"{api_prefix}/inspection-requests/{inspection_request_id}",
    )

    log_api_response(
        "GET",
        f"{api_prefix}/inspection-requests/{inspection_request_id}",
        response,
    )

    assert response.status_code == 200, (
        f"Error al consultar solicitud convertida: "
        f"status_code={response.status_code}, "
        f"response={response.text}"
    )

    return response.json()


def get_inspection(
    client,
    inspection_id,
):
    response = client.get(
        f"{api_prefix}/inspections/{inspection_id}",
    )

    log_api_response(
        "GET",
        f"{api_prefix}/inspections/{inspection_id}",
        response,
    )

    assert response.status_code == 200, (
        f"Error al consultar inspección vinculada: "
        f"status_code={response.status_code}, "
        f"response={response.text}"
    )

    return response.json()


def test_inspection_request_converts_to_linked_inspection(client):
    inspection_request = create_inspection_request(client)
    inspection_request_id = inspection_request["id"]

    assert inspection_request["status"] == "pending"
    assert inspection_request["inspection_id"] is None
    assert inspection_request["company_name"] == "Transportes del Norte S.A.C."
    assert inspection_request["contact_name"] == "María López"
    assert inspection_request["requested_date"] == "2026-07-15"

    inspection = create_inspection(client)
    inspection_id = inspection["id"]

    assert inspection["code"] == "INT-REQUEST-001"
    assert inspection["client_name"] == "Transportes del Norte S.A.C."
    assert inspection["equipment_type"] == "Semirremolque"
    assert inspection["inspection_type"] == "Inspección técnica periódica"
    assert inspection["inspection_date"] == "2026-07-20"
    assert inspection["location"] == "Trujillo"
    assert inspection["requested_by"] == "María López"
    assert inspection["status"] == "draft"

    converted_request = convert_inspection_request(
        client=client,
        inspection_request_id=inspection_request_id,
        inspection_id=inspection_id,
    )

    assert converted_request["id"] == inspection_request_id
    assert converted_request["status"] == "converted"
    assert converted_request["inspection_id"] == inspection_id

    persisted_request = get_inspection_request(
        client=client,
        inspection_request_id=inspection_request_id,
    )

    assert persisted_request["id"] == inspection_request_id
    assert persisted_request["status"] == "converted"
    assert persisted_request["inspection_id"] == inspection_id
    assert persisted_request["company_name"] == "Transportes del Norte S.A.C."

    linked_inspection = get_inspection(
        client=client,
        inspection_id=inspection_id,
    )

    assert linked_inspection["id"] == inspection_id
    assert linked_inspection["code"] == "INT-REQUEST-001"
    assert linked_inspection["client_name"] == "Transportes del Norte S.A.C."

    repeated_conversion_response = client.patch(
        f"{api_prefix}/inspection-requests/{inspection_request_id}/convert",
        json={
            "inspection_id": inspection_id,
        },
    )

    log_api_response(
        "PATCH",
        f"{api_prefix}/inspection-requests/{inspection_request_id}/convert",
        repeated_conversion_response,
    )

    assert repeated_conversion_response.status_code in (200, 400, 409), (
        f"Respuesta inesperada al convertir nuevamente la solicitud: "
        f"status_code={repeated_conversion_response.status_code}, "
        f"response={repeated_conversion_response.text}"
    )

    if repeated_conversion_response.status_code == 200:
        repeated_request = repeated_conversion_response.json()

        assert repeated_request["id"] == inspection_request_id
        assert repeated_request["inspection_id"] == inspection_id
        assert repeated_request["status"] == "converted"