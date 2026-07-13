# MC CLI Domain

MC CLI manages containerized workspaces for Red Hat support investigations, integrating Salesforce case data, Jira ticket data, and isolated per-case cluster access.

## Language

**Investigation**:
The umbrella concept for a unit of work that MC manages. An Investigation is sourced from either a **Case**, a **Ticket**, or both. It gets a workspace, can get a container, and may link to other Investigations through Case-Ticket relationships.
_Avoid_: Work item, task, issue

**Case**:
A Salesforce (SFDC) support case, identified by an 8-digit number (e.g., `04416520`). Tied to a specific **Account** and always has a customer-reported summary. A Case may link to zero or more **Tickets**.
_Avoid_: Ticket, issue, incident (when referring to the SFDC entity)

**Ticket**:
A Jira ticket, identified by a project-key (e.g., `OHSS-52338`). Represents an engineering investigation that may span multiple **Cases** and **Accounts**. A Ticket may link to zero or more Cases.
_Avoid_: Case, issue, bug (when referring to the Jira entity)

**Account**:
The customer organization in Salesforce. One Account has many **Cases**. Used to group Case workspaces on disk (e.g., `cases/Acme_Corp/`).
_Avoid_: Customer, client, org (in code — "customer" is acceptable in UI/logs)

**Workspace**:
The directory tree on the host filesystem where artifacts for an **Investigation** are stored. Workspace artifacts are primarily consumed by the **Investigator** so completeness and machine-readability are prioritized over human-friendly formatting. Two workspace types exist:

- **Case Workspace**: `~/mc/cases/{account}/{case}-{summary}/` — contains SFDC artifacts under `sfdc/` and notes. Does NOT contain Jira data; linked **Tickets** are resolved via the SQLite `case_ticket_links` table.
- **Ticket Workspace**: `~/mc/jira/{ticket-id}/` — contains the Jira ticket JSON and notes. ALL Jira data lives here, regardless of whether the Ticket is linked to a Case.

_Avoid_: Project, directory, folder

**Agents**:
The collective term for AI assistants running inside the container. Each agent has a specific role within the **Workspace**.
_Avoid_: Bots, assistants

**Investigator**:
The primary **Agent** — an AI (Claude Code) running inside the container that reviews **Case** and **Ticket** artifacts to investigate the issue. Workspace artifacts are structured for machine consumption so the Investigator can build context from SFDC data, Jira ticket data, cluster state, and notes.
_Avoid_: Case agent, analyst, bot

## Example dialogue

> **Dev**: "A customer opened a case and there's already a Jira for it — where do the Jira artifacts go?"
>
> **Domain expert**: "Into the Case's Workspace, under `jira/{ticket-id}/`. The Case is the primary Investigation because there's a customer and an Account. The Ticket data is pulled in as supplementary context."
>
> **Dev**: "What if I'm starting from the Jira side and there's no case yet?"
>
> **Domain expert**: "Then the Ticket is the Investigation. It gets its own Workspace under `~/mc/jira/{ticket-id}/`. If a Case gets linked later, mc can associate them — the Ticket Workspace stays where it is, and the Case Workspace gets the Jira artifacts copied in."
>
> **Dev**: "What about a Jira that spans three cases for different customers?"
>
> **Domain expert**: "Each Case has its own Workspace — you investigate each customer's cluster individually. The Jira artifacts get pulled into each Case Workspace independently. The SQLite index tracks which Tickets link to which Cases so you can navigate between them."
