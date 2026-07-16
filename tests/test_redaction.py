from code_analyzer.redaction import redact


def test_redacts_anthropic_and_openai_keys():
    text = 'k1 = "sk-ant-api03-ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"\nk2 = "sk-ABCDEFGHIJKLMNOPQRSTUVWXYZ012345"'
    out = redact(text)
    assert "sk-ant-" not in out.text
    assert "sk-ABCDEFGHIJKLMNOPQRST" not in out.text
    assert out.count >= 2
    assert "REDACTED" in out.text


def test_redacts_private_key_block():
    text = "-----BEGIN RSA PRIVATE KEY-----\nMIIEpAIBAAKCAQEA...\n-----END RSA PRIVATE KEY-----"
    out = redact(text)
    assert "PRIVATE KEY" not in out.text
    assert out.count == 1


def test_redacts_url_credentials_but_keeps_scheme_and_host():
    text = "jdbc:postgresql://dbuser:s3cr3tPass@db.internal:5432/app"
    out = redact(text)
    assert "s3cr3tPass" not in out.text
    assert "db.internal" in out.text          # host preserved
    assert "postgresql://" in out.text        # scheme preserved


def test_redacts_quoted_assigned_secret():
    text = 'password = "hunter2secret"\napi_key: "abcd1234efgh"'
    out = redact(text)
    assert "hunter2secret" not in out.text
    assert "abcd1234efgh" not in out.text
    # the key name is preserved so structure stays legible
    assert "password" in out.text


def test_does_not_mangle_ordinary_code():
    code = (
        "public int add(int a, int b) { return a + b; }\n"
        "String token = getToken();\n"          # unquoted -> not a literal secret
        "int count = items.size();\n"
    )
    out = redact(code)
    assert out.count == 0
    assert out.text == code


def test_aws_github_and_jwt():
    text = (
        "aws = AKIAIOSFODNN7EXAMPLE\n"
        "gh = ghp_1234567890abcdefghijklmnopqrstuvwxyzABCD\n"
        "jwt = eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c"
    )
    out = redact(text)
    assert "AKIAIOSFODNN7EXAMPLE" not in out.text
    assert "ghp_1234567890" not in out.text
    assert "eyJhbGciOiJIUzI1NiJ9" not in out.text
    assert out.count >= 3
