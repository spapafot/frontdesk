# AI Customer Support Platform — Incremental Build Plan

## Goal

Build an AI customer support platform that starts as a local chat-based assistant and gradually evolves into a voice phone agent.

The first version should prove that the AI can answer accurately using only:

- company data stored in PostgreSQL
- documents indexed with pgvector
- explicit tool calls
- no hallucinated answers

The system should first work for a ferry-company use case, then expand into reusable business modules such as clinics, hotels, car rentals, travel agencies, and other customer-support-heavy businesses.

---

## Core Principle

The AI should not be treated as a generic chatbot.

It should behave like a constrained support agent that can only answer from:

1. structured database queries
2. retrieved knowledge base chunks
3. explicitly registered tools
4. human handoff rules

If it cannot answer confidently, it should say so and escalate.

---

## Target Tech Stack

### Backend

- FastAPI
- PostgreSQL
- pgvector
- SQLAlchemy or SQLModel
- Alembic
- Repository pattern
- Streaming responses
- DeepSeek API for local/text MVP
- Later: OpenAI realtime/voice models

### Frontend

- React
- Vite
- TypeScript
- SWR
- Tailwind
- shadcn/ui optional

### AI / Retrieval

- DeepSeek for text reasoning and tool calling in MVP
- pgvector for semantic search
- embeddings for knowledge base chunks
- later OpenAI voice models for speech-to-speech

---

# Phase 1 — Local Chat MVP

## Objective

Create a local chat interface where a user can ask questions and receive answers based on manually inserted business data.

Example questions:

- “When is the next ferry to Corfu?”
- “Do you carry pets?”
- “How much does a car cost?”
- “When is the last ferry next Wednesday?”

## Features

- React chat UI
- FastAPI `/chat/stream` endpoint
- Streaming assistant responses
- Basic conversation history
- Manual seed data in PostgreSQL
- DeepSeek model integration
- Tool calling layer
- Repository pattern for database access

## Backend Structure

```text
backend/
  app/
    main.py
    core/
      config.py
      db.py
    api/
      routes/
        chat.py
        health.py
    services/
      chat_service.py
      rag_service.py
      tool_service.py
    repositories/
      business_repository.py
      knowledge_repository.py
      ferry_repository.py
      conversation_repository.py
    models/
      business.py
      knowledge.py
      ferry.py
      conversation.py
    schemas/
      chat.py
      business.py
      ferry.py
    tools/
      ferry_tools.py
      knowledge_tools.py
    prompts/
      system_prompt.py
    migrations/
```

## Frontend Structure

```text
frontend/
  src/
    api/
      client.ts
      chat.ts
    components/
      ChatWindow.tsx
      MessageBubble.tsx
      ChatInput.tsx
    pages/
      ChatPage.tsx
    hooks/
      useChatStream.ts
    App.tsx
```

## Minimum Database Tables

```sql
businesses
- id
- name
- type
- timezone
- default_language
- created_at
- updated_at
```

```sql
knowledge_documents
- id
- business_id
- title
- type
- content
- is_active
- created_at
- updated_at
```

```sql
knowledge_chunks
- id
- business_id
- document_id
- content
- embedding vector
- metadata jsonb
- created_at
```

```sql
routes
- id
- business_id
- origin
- destination
- active
```

```sql
vessels
- id
- business_id
- name
- supports_vehicles
- supports_pets
- active
```

```sql
schedules
- id
- business_id
- route_id
- vessel_id
- departure_time
- arrival_time
- valid_from
- valid_until
- days_of_week int[]
- active
```

```sql
price_rules
- id
- business_id
- route_id
- passenger_type
- vehicle_type
- price
- currency
- valid_from
- valid_until
- active
```

```sql
conversations
- id
- business_id
- channel -- chat, voice, phone
- started_at
- ended_at
- summary
```

```sql
conversation_messages
- id
- conversation_id
- role -- user, assistant, tool
- content
- tool_name
- metadata jsonb
- created_at
```

## Tools for Phase 1

```text
search_knowledge_base(query)
get_routes()
get_schedule(route, date)
get_next_departure(route, datetime)
get_last_departure(route, date)
calculate_price(route, passengers, vehicle_type, date)
```

## Exit Criteria

Move to Phase 2 only when:

- the chat UI streams answers properly
- the AI can answer simple FAQ questions from the knowledge base
- the AI can query schedules and prices through tools
- answers are grounded in retrieved data
- the AI refuses or escalates when data is missing

---

# Phase 2 — RAG and Guardrails

## Objective

Make the assistant more reliable by improving retrieval, citations, confidence checks, and fallback behavior.

## Features

- Document chunking
- Embedding generation
- pgvector similarity search
- metadata filtering by business/module
- confidence threshold
- “I don’t know” fallback
- answer source tracking
- admin-only debug panel showing retrieved chunks and tool calls

## Retrieval Flow

```text
User question
  ↓
Classify intent
  ↓
Choose tool or RAG search
  ↓
Retrieve relevant data
  ↓
Generate answer using only retrieved context
  ↓
Store messages, tool calls, and sources
```

## Guardrail Rules

The assistant must:

- not invent prices
- not invent schedules
- not invent policies
- ask follow-up questions when required data is missing
- escalate when confidence is low
- clearly state when information is unavailable

## Exit Criteria

Move to Phase 3 only when:

- hallucinations are rare in test scenarios
- retrieved chunks are visible in debug mode
- tool calls are logged
- missing-data cases are handled safely

---

# Phase 3 — Admin Knowledge Base Upload

## Objective

Allow a business user to upload and manage their own knowledge base instead of manually inserting data.

## Features

- Admin dashboard
- Create/edit/delete knowledge documents
- Upload text, markdown, PDF later
- Re-index documents after editing
- Toggle documents active/inactive
- Preview chunks
- Test assistant against uploaded data

## Admin Screens

```text
Business Settings
Knowledge Base
Test Chat
Conversation Logs
```

## Initial Upload Types

Start simple:

- plain text
- markdown
- copy/paste FAQ

Add later:

- PDF
- DOCX
- CSV
- website crawler

## Exit Criteria

Move to Phase 4 only when:

- a user can add knowledge without developer help
- uploaded content is searchable through pgvector
- the assistant uses new knowledge immediately or after re-indexing

---

# Phase 4 — Ferry Module

## Objective

Create the first industry-specific module: ferry companies.

This module should support structured data that cannot be handled safely with generic RAG.

## Ferry Admin Screens

```text
Routes
Vessels
Schedules
Prices
Policies
Announcements
```

## Ferry-Specific Features

- route management
- vessel management
- timetable creation
- date-valid schedules
- days-of-week schedules
- passenger and vehicle pricing
- pet policy
- delay/cancellation announcements
- seasonal schedule support

## Ferry Tools

```text
get_next_departure
get_last_departure
get_departures_for_date
calculate_ferry_price
check_pet_policy
check_vehicle_policy
get_current_announcements
```

## Example Questions to Support

```text
“When is the next ferry to Corfu?”
“When is the last ferry next Wednesday?”
“How much for 2 adults and a car?”
“Can I bring my dog?”
“Is there a ferry after 9 PM?”
“Do you carry motorcycles?”
```

## Exit Criteria

Move to Phase 5 only when:

- ferry company data can be edited from the dashboard
- common ferry questions work reliably
- the assistant asks follow-up questions for missing route/date/vehicle info
- the assistant uses SQL tools for exact data and RAG for policies

---

# Phase 5 — Business Modules System

## Objective

Generalize the architecture so different industries can have their own modules.

## Module Concept

Each module should define:

- database tables
- admin screens
- available tools
- prompt instructions
- supported intents
- validation rules

## Example Modules

```text
ferry_company
clinic
hotel
car_rental
travel_agency
restaurant
municipality
```

## Module Registry Example

```python
MODULES = {
    "ferry_company": {
        "tools": ferry_tools,
        "system_prompt": ferry_prompt,
        "admin_sections": ["routes", "schedules", "prices", "policies"],
    },
    "clinic": {
        "tools": clinic_tools,
        "system_prompt": clinic_prompt,
        "admin_sections": ["services", "doctors", "opening_hours", "policies"],
    },
}
```

## Exit Criteria

Move to Phase 6 only when:

- one business can use the ferry module
- another test business can use a simpler generic module
- tools are loaded based on business type
- prompts are module-specific

---

# Phase 6 — Conversation Logs and Analytics

## Objective

Turn conversations into business value.

## Features

- conversation history
- call/chat summaries
- top questions
- unresolved questions
- transfer/escalation rate
- missing knowledge suggestions
- customer intent categories

## Tables

```sql
conversation_intents
- id
- conversation_id
- intent
- confidence
- created_at
```

```sql
unanswered_questions
- id
- business_id
- question
- suggested_document_title
- status
- created_at
```

## Useful Analytics

```text
Top questions this week
Most common unresolved questions
Average conversation duration
Escalation rate
Most requested routes
Most requested dates
Most requested policies
```

## Exit Criteria

Move to Phase 7 only when:

- every conversation is logged
- summaries are generated
- unanswered questions are visible to the admin
- admins can improve the knowledge base based on real conversations

---

# Phase 7 — Local Speech Prototype

## Objective

Test voice locally without phone integration.

The user speaks into the browser microphone, the AI responds with voice, but the system still runs through the same backend, tools, and knowledge base.

## Features

- browser microphone input
- speech-to-text
- existing chat/tool pipeline
- text-to-speech response
- voice playback in browser
- transcript shown in chat UI

## Architecture

```text
Browser mic
  ↓
Speech-to-text
  ↓
FastAPI chat/tool pipeline
  ↓
Assistant text response
  ↓
Text-to-speech
  ↓
Browser audio playback
```

## Important Requirement

Do not build separate logic for voice.

Voice should use the same:

- tools
- repositories
- knowledge base
- prompts
- guardrails
- conversation logging

## Exit Criteria

Move to Phase 8 only when:

- local voice works end-to-end
- interruptions and corrections are handled reasonably
- transcripts are saved
- same answers work in both chat and voice

---

# Phase 8 — OpenAI Realtime Voice

## Objective

Replace the local speech pipeline with a realtime voice experience using OpenAI voice models.

## Features

- low-latency voice interaction
- interruption support
- Greek language testing
- tool calling through backend
- conversation transcript
- fallback to text chat

## Architecture

```text
Browser audio
  ↓
OpenAI Realtime session
  ↓
FastAPI tool bridge
  ↓
PostgreSQL / pgvector
  ↓
Realtime spoken answer
```

## Exit Criteria

Move to Phase 9 only when:

- Greek voice quality is acceptable
- latency feels natural
- tool calls work during realtime voice conversations
- the assistant does not bypass business rules

---

# Phase 9 — Phone Integration

## Objective

Connect the AI agent to an actual phone number through a telephony provider.

## Features

- virtual phone number
- inbound calls
- audio streaming to AI
- call transcript
- human handoff
- call recording optional
- business hours routing

## Architecture

```text
Caller
  ↓
Virtual phone number / SIP provider
  ↓
Audio stream
  ↓
OpenAI realtime voice model
  ↓
FastAPI tool bridge
  ↓
PostgreSQL / pgvector
  ↓
Spoken answer
```

## Human Handoff

```text
AI cannot answer
  ↓
Summarize caller request
  ↓
Transfer to business phone
  ↓
Store transcript and summary
```

## Exit Criteria

Move to Phase 10 only when:

- inbound phone calls work
- the AI can answer common questions by phone
- transfer to human works
- transcripts and summaries are stored
- business can review calls afterward

---

# Phase 10 — Productionization

## Objective

Prepare the platform for real customers.

## Required Features

- authentication
- multi-tenant business isolation
- roles and permissions
- billing plans
- usage metering
- rate limits
- observability
- error monitoring
- audit logs
- backups
- GDPR/privacy review

## Production Concerns

- never leak one business's data to another
- encrypt sensitive data
- protect call recordings and transcripts
- support deletion requests
- log tool calls for auditability
- allow businesses to disable AI instantly
- create safe fallback to human phone line

---

# Suggested MVP Milestones

## Milestone 1

Local text chat answers ferry FAQs from seeded knowledge base.

## Milestone 2

Assistant queries structured ferry schedules and prices through tools.

## Milestone 3

Admin can upload/edit knowledge base content.

## Milestone 4

Ferry module supports schedules, prices, policies, and announcements.

## Milestone 5

Conversation logs and unanswered-question analytics.

## Milestone 6

Browser-based speech test.

## Milestone 7

OpenAI realtime voice test.

## Milestone 8

Phone number integration with human handoff.

---

# Initial Demo Dataset

Use a fake ferry company:

```text
Business: Ionian Demo Ferries
Routes:
- Igoumenitsa → Corfu
- Corfu → Igoumenitsa
- Igoumenitsa → Lefkimmi
- Lefkimmi → Igoumenitsa
```

Policies:

```text
Pets are allowed on board but must remain in designated areas.
Cars, motorcycles, vans, and bicycles are supported.
Passengers should arrive 30 minutes before departure.
Vehicles should arrive 45 minutes before departure.
Tickets are refundable up to 24 hours before departure.
```

Example timetable:

```text
Igoumenitsa → Corfu
Monday-Sunday:
07:30, 10:00, 13:00, 16:00, 19:30, 22:00
```

Example prices:

```text
Adult passenger: €6.50
Child passenger: €3.50
Car: €24.00
Motorcycle: €8.00
Bicycle: €3.00
```

---

# Recommended First Sprint

## Backend

- Create FastAPI project
- Add PostgreSQL + pgvector
- Add Alembic
- Create core tables
- Seed ferry demo data
- Add DeepSeek chat service
- Add `/chat/stream`
- Add ferry tools
- Add basic RAG search

## Frontend

- Create Vite React app
- Add Tailwind
- Create chat UI
- Stream assistant responses
- Show debug panel with retrieved chunks and tool calls

## Test Questions

```text
When is the next ferry to Corfu?
When is the last ferry tomorrow?
How much for 2 adults and a car?
Can I bring my dog?
What time should I arrive with a vehicle?
Can I get a refund?
```

---

# Long-Term Product Direction

The final product should not be marketed as a chatbot.

It should be marketed as:

> An AI receptionist trained on your business data that answers customers, handles repetitive questions, and transfers complex cases to your team.

The strongest differentiator is not the voice model.

The strongest differentiator is the business-specific module system:

- ferry schedules
- clinic appointments
- hotel policies
- car rental availability
- travel agency services
- restaurant reservations

Voice and phone integration are the final layer, not the core product.
