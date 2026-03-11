"""
Boilerplate removal – modular rules that strip noise from HTML before content extraction.

Each rule is a callable (soup) -> None that mutates the soup in place.
Rules are applied in order.
"""
import re
from typing import Callable, List

from bs4 import BeautifulSoup, Tag


Rule = Callable[[BeautifulSoup], None]


def remove_scripts_and_styles(soup: BeautifulSoup) -> None:
    for tag in soup.find_all(["script", "style", "noscript", "link"]):
        tag.decompose()


def remove_nav_header_footer(soup: BeautifulSoup) -> None:
    for tag in soup.find_all(["nav", "header", "footer"]):
        tag.decompose()


def remove_hidden_elements(soup: BeautifulSoup) -> None:
    for tag in soup.find_all(style=re.compile(r"display\s*:\s*none", re.I)):
        tag.decompose()
    for tag in soup.find_all(attrs={"hidden": True}):
        tag.decompose()
    for tag in soup.find_all(attrs={"aria-hidden": "true"}):
        tag.decompose()


def remove_cookie_banners(soup: BeautifulSoup) -> None:
    patterns = re.compile(
        r"cookie|consent|gdpr|cc-banner|cookie-notice|cookie-bar|onetrust",
        re.I,
    )
    for tag in soup.find_all(True, {"class": patterns}):
        tag.decompose()
    for tag in soup.find_all(True, {"id": patterns}):
        tag.decompose()


def remove_newsletter_blocks(soup: BeautifulSoup) -> None:
    patterns = re.compile(r"newsletter|nieuwsbrief|subscribe|mailchimp|signup-form", re.I)
    for tag in soup.find_all(True, {"class": patterns}):
        tag.decompose()
    for tag in soup.find_all(True, {"id": patterns}):
        tag.decompose()


def remove_social_share(soup: BeautifulSoup) -> None:
    patterns = re.compile(r"social|share|sharing|follow-us|social-links", re.I)
    for tag in soup.find_all(True, {"class": patterns}):
        tag.decompose()


def remove_related_posts(soup: BeautifulSoup) -> None:
    patterns = re.compile(r"related|gerelateerd|similar|also-like|sidebar", re.I)
    for tag in soup.find_all(True, {"class": patterns}):
        tag.decompose()
    for tag in soup.find_all(["aside"]):
        tag.decompose()


def remove_iframes_and_embeds(soup: BeautifulSoup) -> None:
    for tag in soup.find_all(["iframe", "embed", "object", "video", "audio"]):
        tag.decompose()


def remove_breadcrumbs(soup: BeautifulSoup) -> None:
    patterns = re.compile(r"breadcrumb", re.I)
    for tag in soup.find_all(True, {"class": patterns}):
        tag.decompose()
    for tag in soup.find_all(True, {"aria-label": re.compile(r"breadcrumb", re.I)}):
        tag.decompose()


def remove_login_account(soup: BeautifulSoup) -> None:
    patterns = re.compile(r"login|account|sign-?in|sign-?up|my-?account|auth", re.I)
    for tag in soup.find_all(True, {"class": patterns}):
        tag.decompose()
    for tag in soup.find_all(True, {"id": patterns}):
        tag.decompose()


DEFAULT_RULES: List[Rule] = [
    remove_scripts_and_styles,
    remove_hidden_elements,
    remove_nav_header_footer,
    remove_cookie_banners,
    remove_newsletter_blocks,
    remove_social_share,
    remove_related_posts,
    remove_iframes_and_embeds,
    remove_breadcrumbs,
    remove_login_account,
]


class BoilerplateRemover:
    """Apply a chain of boilerplate removal rules to a BeautifulSoup tree."""

    def __init__(self, extra_rules: List[Rule] | None = None):
        self.rules = list(DEFAULT_RULES)
        if extra_rules:
            self.rules.extend(extra_rules)

    def clean(self, soup: BeautifulSoup) -> BeautifulSoup:
        for rule in self.rules:
            rule(soup)
        return soup
