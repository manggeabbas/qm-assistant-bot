"""Typed application errors."""

from __future__ import annotations


class QMTrainingError(Exception):
    """Base error for the project."""


class SchemaError(QMTrainingError):
    """Structured data does not satisfy the required schema."""


class MaterialError(QMTrainingError):
    """Material could not be read or normalized."""


class UnsupportedMaterialError(MaterialError):
    """The material format is not supported."""


class AIProviderError(QMTrainingError):
    """The AI provider failed or returned unusable content."""


class AIValidationError(AIProviderError):
    """The AI response does not satisfy the required schema."""


class DocumentGenerationError(QMTrainingError):
    """The document could not be generated."""


class ConversionError(QMTrainingError):
    """DOCX -> PDF conversion failed."""


class ValidationError(QMTrainingError):
    """Document validation failed."""


class AuthorizationError(QMTrainingError):
    """The user is not allowed to use the bot."""


class SessionError(QMTrainingError):
    """Session state is invalid."""
