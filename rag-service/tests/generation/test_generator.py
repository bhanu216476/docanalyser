from unittest.mock import Mock
from types import SimpleNamespace

from app.context.models import StructuredContext
from app.generation.generator import AnswerGenerator
from app.generation.models import GenerationRequest
from app.generation.prompt import PromptBuilder


def test_generator_calls_client_once_and_maps_response() -> None:
    client = Mock()
    client.generate.return_value = SimpleNamespace(
        text="The answer [1]",
        model="test-model",
        input_tokens=10,
        output_tokens=4,
        total_tokens=14,
    )
    builder = Mock(spec=PromptBuilder)
    builder.build.return_value = "prompt"
    generator = AnswerGenerator(client, builder)
    request = GenerationRequest(query="Question", context=StructuredContext())

    answer = generator.generate(request)

    builder.build.assert_called_once_with("Question", request.context)
    client.generate.assert_called_once_with("prompt")
    assert answer.answer == "The answer [1]"
    assert answer.model == "test-model"
    assert answer.input_tokens == 10
    assert answer.output_tokens == 4
    assert answer.total_tokens == 14


def test_generator_does_not_retrieve_or_rerank() -> None:
    client = Mock()
    client.generate.return_value = SimpleNamespace(
        text="insufficient",
        model="test-model",
        input_tokens=None,
        output_tokens=None,
        total_tokens=None,
    )
    builder = PromptBuilder()

    answer = AnswerGenerator(client, builder).generate(
        GenerationRequest(query="Question", context=StructuredContext())
    )

    assert answer.answer == "insufficient"
    client.generate.assert_called_once()