# CargoPulse: Architecture & Product Documentation

Welcome to the definitive architecture, specification, and implementation blueprint for **CargoPulse** — an enterprise-grade, accountable B2B logistics coordination and execution platform.

---

## Document Index

| Document | Title | Description |
|---|---|---|
| [01. Product Requirements Document](file:///d:/Founding-Projects/cargopulse/docs/01_PRODUCT_REQUIREMENTS_DOCUMENT.md) | **Product Requirements Document (PRD)** | High-level product vision, core problem statements, target personas, multi-tenancy principles, and scope boundaries. |
| [02. Functional Requirements](file:///d:/Founding-Projects/cargopulse/docs/02_FUNCTIONAL_REQUIREMENTS.md) | **Functional Requirements Specification** | Deep-dive capability requirements across all 20 core platform modules. |
| [03. Non-Functional Requirements](file:///d:/Founding-Projects/cargopulse/docs/03_NON_FUNCTIONAL_REQUIREMENTS.md) | **Non-Functional Requirements (NFRs)** | Performance SLAs, high availability, reliability, disaster recovery, data retention, and compliance. |
| [04. Roles & Permissions Matrix](file:///d:/Founding-Projects/cargopulse/docs/04_ROLES_PERMISSIONS_MATRIX.md) | **RBAC & Authorization Matrix** | Multi-tenant tenant-level and role-level privilege hierarchies and granular action matrix. |
| [05. Business Workflows & State Machines](file:///d:/Founding-Projects/cargopulse/docs/05_BUSINESS_WORKFLOWS.md) | **Business Workflows & State Machines** | Detailed lifecycles (Shipment, Booking, Pickup, Exception, POD, Reconciliation) with state transition diagrams. |
| [06. Database ERD & Schema Design](file:///d:/Founding-Projects/cargopulse/docs/06_DATABASE_ERD_DESIGN.md) | **Database ERD & Storage Architecture** | PostgreSQL relational schema, indexes, multi-tenancy partition key strategy, and immutable audit event ledger. |
| [07. API Module Plan](file:///d:/Founding-Projects/cargopulse/docs/07_API_MODULE_PLAN.md) | **API Architecture & Endpoint Blueprint** | Comprehensive RESTful and WebSocket endpoint plan covering all 20 modules with standard error envelope schemas. |
| [08. Frontend Screen Inventory](file:///d:/Founding-Projects/cargopulse/docs/08_FRONTEND_SCREEN_INVENTORY.md) | **Frontend Screen Inventory & UX Flows** | React/Vite/Tailwind/shadcn screen catalog, component tree, layout structure, and form validation schemas. |
| [09. Security Architecture](file:///d:/Founding-Projects/cargopulse/docs/09_SECURITY_ARCHITECTURE.md) | **Security Architecture & Data Protection** | Row-level tenant isolation, JWT authentication, RBAC policy enforcement, webhook HMAC signing, and encryption. |
| [10. Testing Strategy](file:///d:/Founding-Projects/cargopulse/docs/10_TESTING_STRATEGY.md) | **Comprehensive QA & Testing Strategy** | Pytest unit/integration tests, Vitest UI unit tests, Playwright E2E suites, and test data management. |
| [11. Development Phases](file:///d:/Founding-Projects/cargopulse/docs/11_DEVELOPMENT_PHASES.md) | **Phased Implementation Roadmap** | Step-by-step milestone schedule from core infrastructure through full deployment. |
| [12. Module Acceptance Criteria](file:///d:/Founding-Projects/cargopulse/docs/12_ACCEPTANCE_CRITERIA.md) | **Acceptance Criteria (Gherkin/BDD)** | Concrete Given-When-Then acceptance criteria for every one of the 20 modules. |
| [13. Ambiguities & Sensible Defaults](file:///d:/Founding-Projects/cargopulse/docs/13_AMBIGUITIES_AND_SENSIBLE_DEFAULTS.md) | **Ambiguities & Architectural Defaults** | Systematic analysis of logistical domain edge cases with battle-tested architectural defaults. |

---

## Architectural Principles Summary

1. **Strict Multi-Tenancy**: Logical tenant isolation enforced at the database level (`tenant_id` on all tenant-scoped tables with foreign keys and index compound keys, plus query interceptors).
2. **Accountability & Immutability**: All shipment state changes, driver arrivals, gate movements, and exception logs are committed as immutable event logs in an audit ledger table alongside state tables.
3. **Fail-Fast Recovery**: Pickup commitments have strict SLA timers backed by Celery beat tasks that auto-trigger exception escalation and recovery matching when transporters fail to show up.
4. **PostgreSQL as Source of Truth**: Relational integrity with transactions for critical business mutations; Redis dedicated strictly to caching, pub/sub, rate limiting, and Celery broker queues.
5. **No Production Placeholders**: All schemas, validation rules, APIs, and business services adhere to enterprise B2B production standards with full test verification.
