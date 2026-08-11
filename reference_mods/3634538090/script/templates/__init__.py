from dataclasses import dataclass

_TAG_TEMPLATE = ' '*4*3 + 'has_or_had_tag = {tag}'

def make_tags(tags: list[str]) -> str:
    return '\n'.join(_TAG_TEMPLATE.format(tag=tag) for tag in tags)

@dataclass(frozen=True)
class TemplateData:
    NAMESPACE: str
    LOCALIZATION_TEMPLATE: str
    EVENT_TEMPLATE: str