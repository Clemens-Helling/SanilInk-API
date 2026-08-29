from app.core.database import Base


def test_anonymous_intake_tables_exist_in_metadata():
    table_names = {table.name for table in Base.metadata.tables.values()}

    assert "intake_keys" in table_names
    assert "pending_intakes" in table_names

    intake_keys = Base.metadata.tables["intake_keys"]
    pending_intakes = Base.metadata.tables["pending_intakes"]

    assert "intake_key_id" in intake_keys.columns
    assert "public_key" in intake_keys.columns
    assert "encrypted_private_key" in intake_keys.columns
    assert "revoked_at" in intake_keys.columns

    assert "pending_intake_id" in pending_intakes.columns
    assert "intake_key_id" in pending_intakes.columns
    assert "sealed_payload" in pending_intakes.columns
    assert "status" in pending_intakes.columns
