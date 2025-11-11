# BettaFish Migration Specifications

This directory contains comprehensive specifications for migrating the BettaFish multi-agent public opinion analysis system to modern agentic frameworks.

## Overview

BettaFish is a sophisticated multi-agent system for public opinion analysis that currently uses:
- Flask orchestrator managing 4 Streamlit subprocesses
- File-based agent coordination via ForumEngine
- Node-based agent architecture with search, analysis, and reporting capabilities
- Multiple LLM providers and external tool integrations

## Migration Goal

Modernize BettaFish architecture using a hybrid approach with **LangGraph for agent orchestration** and **DBOS Python for state management** while preserving:
- Multi-agent coordination capabilities
- Public opinion analysis functionality
- External tool integrations (Tavily, Bocha AI, multiple LLMs)
- Database schema and existing data
- Professional report generation templates

## Specification Structure

```
docs/specs/
├── README.md                    # This file
├── requirements/                # Functional and non-functional requirements
│   ├── functional.md           # Functional requirements specification
│   └── non-functional.md       # Performance, security, scalability requirements
├── architecture/               # System and technical architecture
│   ├── system-design.md        # Overall system architecture
│   ├── technology-stack.md     # Technology choices and rationale
│   └── component-design.md     # Individual component specifications
├── interfaces/                 # API and data interface specifications
│   ├── api-specification.md    # REST API and WebSocket interfaces
│   ├── data-models.md         # Data models and state management
│   └── tool-interfaces.md     # External tool integration interfaces
├── implementation/             # Implementation and migration strategy
│   ├── migration-roadmap.md    # Detailed phased migration plan
│   ├── testing-strategy.md     # Testing approach and acceptance criteria
│   └── code-patterns.md        # Coding standards and patterns
├── deployment/                 # Deployment and infrastructure specifications
│   ├── container-architecture.md # Docker and deployment setup
│   ├── infrastructure.md       # Infrastructure requirements
│   └── monitoring.md          # Observability and monitoring
└── governance/                # Development and maintenance governance
    ├── development-standards.md # Coding standards and practices
    ├── maintenance-procedures.md # Ongoing maintenance guidelines
    └── extension-guidelines.md  # Adding new agents and features
```

## Migration Framework

**Target Framework**: LangGraph 1.0+
**Migration Pattern**: StateGraph-based agent orchestration
**Communication**: Framework-native messaging (replacing file-based coordination)
**State Management**: TypedDict with persistence
**Processing**: Async/await patterns for I/O operations

## Key Benefits

- **Improved Reliability**: Framework-native error handling and retry mechanisms
- **Better Performance**: Async processing and optimized state management
- **Enhanced Scalability**: Horizontal scaling and resource management
- **Modern Architecture**: Industry-standard patterns and tooling
- **Easier Maintenance**: Clear separation of concerns and documented interfaces

## Validation Approach

Each specification includes:
- Clear acceptance criteria
- Measurable success metrics
- Risk mitigation strategies
- Testing requirements

## Next Steps

1. Review all specification documents
2. Validate requirements with stakeholders
3. Set up development environment
4. Begin Phase 1 implementation following migration roadmap

---

*This specification set provides a complete roadmap for modernizing BettaFish while preserving its unique multi-agent coordination and public opinion analysis capabilities.*