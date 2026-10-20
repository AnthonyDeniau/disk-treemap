# Security policy

For a vulnerability, use the repository's **Security → Report a vulnerability**
feature if enabled. If unavailable, open an issue asking for a private contact,
without publishing exploit details or sensitive reports. Do not attach real
filesystem exports, credentials, private paths or file contents to public issues.

The current `0.1.x` line receives security fixes. This is an early release, not
a security boundary for hostile filesystems. Run it with normal user privileges.

Reports intentionally contain filesystem metadata. Keep them private. The
scanner never needs Keychain credentials or API keys; requests for them are not
part of this project's workflow.
