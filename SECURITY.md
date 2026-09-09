# Security policy

## Reporting a vulnerability

Please report vulnerabilities privately through the repository owner's GitHub profile rather than opening a public issue. Include the affected path, impact, and a minimal reproduction. Do not attach credentials, private documents, or unredacted logs.

## Safe handling

Keep API, OSS, and database credentials in local ignored environment files. If a secret appears in a working tree or Git history, revoke and rotate it promptly, then contact the maintainer privately. CI intentionally runs without provider credentials and does not claim hosted production security.
