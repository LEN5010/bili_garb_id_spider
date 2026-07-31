from bili_garb_id_spider.login import credentials_from_cookie_dict


class FakeCredential:
    sessdata = "attribute-session"
    bili_jct = "attribute-csrf"
    buvid3 = "attribute-device"
    dedeuserid = "10001"
    ac_time_value = "attribute-refresh"


def test_cookie_keys_are_case_insensitive() -> None:
    credentials = credentials_from_cookie_dict(
        {
            "sessdata": "cookie-session",
            "BILI_JCT": "cookie-csrf",
            "BUVID3": "cookie-device",
            "dedeuserid": "10002",
        }
    )
    assert credentials.sessdata == "cookie-session"
    assert credentials.bili_jct == "cookie-csrf"
    assert credentials.buvid3 == "cookie-device"
    assert credentials.dede_user_id == "10002"


def test_credential_attributes_are_used_as_fallback() -> None:
    credentials = credentials_from_cookie_dict({}, FakeCredential())
    assert credentials.sessdata == "attribute-session"
    assert credentials.bili_jct == "attribute-csrf"
    assert credentials.buvid3 == "attribute-device"
    assert credentials.dede_user_id == "10001"
    assert credentials.ac_time_value == "attribute-refresh"
