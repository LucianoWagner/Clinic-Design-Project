from app.agents.response_sanitizer import StreamingFunctionCallSanitizer, sanitize_agent_response


def test_sanitizer_removes_function_block_and_keeps_human_text() -> None:
    response = sanitize_agent_response(
        'Puedo ayudarte. <function=search_availability>{"specialty_name":"cardiologia"}</function>'
    )

    assert response.was_sanitized is True
    assert response.text == "Puedo ayudarte."


def test_sanitizer_leaves_normal_response_unchanged() -> None:
    response = sanitize_agent_response("Tenemos cardiología, clínica y dermatología.")

    assert response.was_sanitized is False
    assert response.text == "Tenemos cardiología, clínica y dermatología."


def test_sanitizer_removes_multiline_function_block() -> None:
    response = sanitize_agent_response(
        """Estas son las opciones:

<function=search_availability>
{"specialty_name":"clinica","limit":5}
</function>

¿Querés que busque un turno?"""
    )

    assert response.was_sanitized is True
    assert "<function" not in response.text
    assert "specialty_name" not in response.text
    assert response.text == "Estas son las opciones:\n\n¿Querés que busque un turno?"


def test_streaming_sanitizer_removes_function_block_across_chunks() -> None:
    sanitizer = StreamingFunctionCallSanitizer()

    output = ""
    output += sanitizer.push("Tenemos cardiología. <func")
    output += sanitizer.push('tion=search_availability>{"specialty_name":"x"}')
    output += sanitizer.push("</function> ¿Querés que busque turnos?")
    output += sanitizer.flush()

    assert sanitizer.was_sanitized is True
    assert output == "Tenemos cardiología.  ¿Querés que busque turnos?"
    assert "<function" not in output
    assert "specialty_name" not in output
