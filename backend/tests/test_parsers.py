from __future__ import annotations

from app.services.parsers import EmailParseContext, ParserRegistry
from app.services.parsers.generic import GenericEmailParser
from app.services.parsers.linkedin import LinkedInEmailParser


def test_registry_selects_linkedin_for_linkedin_job_alert() -> None:
    context = EmailParseContext(
        sender="jobs-listings@linkedin.com",
        subject="PetroMatch, new jobs for drilling engineer",
        html_body='<a href="https://www.linkedin.com/jobs/view/1234567890/?trk=email">Senior Drilling Engineer</a>',
        plain_text_body=None,
    )

    parser = ParserRegistry().select_parser(context)

    assert isinstance(parser, LinkedInEmailParser)


def test_registry_falls_back_to_generic_for_unknown_job_alert() -> None:
    context = EmailParseContext(
        sender="alerts@example.com",
        subject="New oil and gas roles",
        html_body='<a href="https://example.com/careers/jobs/9876">Apply</a>',
        plain_text_body=None,
    )

    parser = ParserRegistry().select_parser(context)

    assert isinstance(parser, GenericEmailParser)


def test_linkedin_parser_extracts_multiple_jobs_from_html() -> None:
    html = """
    <html><body>
      <div>
        <a href="https://www.linkedin.com/jobs/view/1234567890/?trk=email_jobs">Senior Drilling Engineer</a>
        <span>PetroCo</span>
        <span>Houston, TX</span>
      </div>
      <div>
        <a href="https://www.linkedin.com/jobs/view/9876543210/?currentJobId=9876543210&utm_source=email">Subsea Project Manager</a>
        <span>Offshore Energy Ltd</span>
        <span>London, UK</span>
      </div>
      <a href="https://www.linkedin.com/email-preferences">Unsubscribe</a>
    </body></html>
    """
    context = EmailParseContext(
        sender="jobs-listings@linkedin.com",
        subject="Job alert",
        html_body=html,
        plain_text_body=None,
    )

    jobs = LinkedInEmailParser().parse(context)

    assert len(jobs) == 2
    assert jobs[0].source == "linkedin"
    assert jobs[0].job_title == "Senior Drilling Engineer"
    assert jobs[0].company == "PetroCo"
    assert jobs[0].location == "Houston, TX"
    assert jobs[0].external_id == "1234567890"
    assert jobs[1].external_id == "9876543210"


def test_generic_parser_extracts_job_blocks_and_ignores_boilerplate() -> None:
    html = """
    <html><body>
      <section>
        <h2>Pipeline Integrity Engineer</h2>
        <p>Company: Gulf Operators</p>
        <p>Doha, Qatar</p>
        <a href="https://jobs.example.com/job/445566?utm_campaign=alert">Apply now</a>
      </section>
      <section>
        <h2>Maintenance Supervisor</h2>
        <p>North Sea Services</p>
        <p>Aberdeen, UK</p>
        <a href="https://careers.example.org/position/778899">View job</a>
      </section>
      <a href="https://jobs.example.com/unsubscribe">unsubscribe</a>
    </body></html>
    """
    context = EmailParseContext(
        sender="alerts@example.com",
        subject="New jobs",
        html_body=html,
        plain_text_body=None,
    )

    jobs = GenericEmailParser().parse(context)

    assert len(jobs) == 2
    assert jobs[0].job_title == "Pipeline Integrity Engineer"
    assert jobs[0].company == "Gulf Operators"
    assert jobs[0].location == "Doha, Qatar"
    assert jobs[0].job_url == "https://jobs.example.com/job/445566"
    assert jobs[1].job_title == "Maintenance Supervisor"
