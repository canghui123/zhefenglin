from models.legal_document import LegalDocumentGenerateRequest
from services.legal_document_generator import generate_legal_document


def test_generate_civil_complaint_escapes_user_input():
    req = LegalDocumentGenerateRequest(
        document_type="civil_complaint",
        debtor_name="<script>alert(1)</script>",
        creditor_name="车途金融",
        car_description="奥迪A6L 2020款",
        contract_number="HT-001",
        overdue_amount=120000,
    )

    result = generate_legal_document(req)

    assert result.title == "民事起诉状"
    assert "车途金融" in result.html
    assert "奥迪A6L" in result.html
    assert "<script>alert(1)</script>" not in result.html
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in result.html
    assert "民事起诉状" in result.plain_text


def test_generate_special_procedure_application_uses_specific_template():
    req = LegalDocumentGenerateRequest(
        document_type="special_procedure_application",
        debtor_name="张三",
        creditor_name="车途金融",
        car_description="已入库宝马3系",
        overdue_amount=90000,
        vehicle_value=150000,
    )

    result = generate_legal_document(req)

    assert result.title == "实现担保物权特别程序申请书"
    assert "车辆已收回、已入库" in result.html
    assert "150,000.00" in result.html
