from backend.app.services.llm_service import LLMService


def main():
    service = LLMService()

    question = "Explain the approvals required before a production deployment."

    context = """
[Source 1]
Title: Synthetic Deployment and Release Management SOP
Page: 4

All production deployments require a formal Change Request ticket
in ServiceNow.

The following artifacts are required:
- UAT Sign-off
- QA Sign-off
- Deployment Runbook
- Rollback Plan
"""

    answer = service.generate_answer(
        question=question,
        context=context,
    )

    print("\nGenerated Answer:\n")
    print(answer)


if __name__ == "__main__":
    main()