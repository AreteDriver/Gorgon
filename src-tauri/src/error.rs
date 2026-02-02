//! Error types for Gorgon Desktop

use serde::Serialize;
use thiserror::Error;

/// Application error type
#[derive(Debug, Error)]
pub enum Error {
    #[error("IO error: {0}")]
    Io(#[from] std::io::Error),

    #[error("Git error: {0}")]
    Git(#[from] git2::Error),

    #[error("Serialization error: {0}")]
    Serde(#[from] serde_json::Error),

    #[error("Path error: {0}")]
    InvalidPath(String),

    #[error("Operation not allowed: {0}")]
    NotAllowed(String),

    #[error("Git repository not found at path")]
    NoRepository,

    #[error("{0}")]
    Custom(String),
}

/// Result type for commands
pub type Result<T> = std::result::Result<T, Error>;

impl Serialize for Error {
    fn serialize<S>(&self, serializer: S) -> std::result::Result<S::Ok, S::Error>
    where
        S: serde::Serializer,
    {
        serializer.serialize_str(&self.to_string())
    }
}
