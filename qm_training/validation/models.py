"""Validation result models."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ValidationIssue:
    level: str  # "error" | "warning"
    code: str
    message: str


@dataclass
class ValidationReport:
    issues: list[ValidationIssue] = field(default_factory=list)

    def add(self, level: str, code: str, message: str) -> None:
        self.issues.append(ValidationIssue(level, code, message))

    def error(self, code: str, message: str) -> None:
        self.add("error", code, message)

    def warning(self, code: str, message: str) -> None:
        self.add("warning", code, message)

    @property
    def errors(self) -> list[ValidationIssue]:
        return [issue for issue in self.issues if issue.level == "error"]

    @property
    def warnings(self) -> list[ValidationIssue]:
        return [issue for issue in self.issues if issue.level == "warning"]

    @property
    def ok(self) -> bool:
        return not self.errors

    def summary(self) -> str:
        return f"{len(self.errors)} error(s), {len(self.warnings)} warning(s)"
