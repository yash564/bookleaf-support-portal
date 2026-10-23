"""initial schema

Revision ID: 8a5dbdd7c747
Revises: 
Create Date: 2026-10-23 21:24:23.851940

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '0001'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Alembic autogenerate does not emit standalone sequences; tickets.number depends on this one.
    op.execute(sa.schema.CreateSequence(sa.Sequence('ticket_number_seq', start=1001)))
    op.create_table('users',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('email', sa.String(length=255), nullable=False),
    sa.Column('password_hash', sa.String(length=255), nullable=False),
    sa.Column('role', sa.String(length=16), nullable=False),
    sa.Column('name', sa.String(length=120), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_users_email'), 'users', ['email'], unique=True)
    op.create_table('author_profiles',
    sa.Column('id', sa.String(length=16), nullable=False),
    sa.Column('user_id', sa.Uuid(), nullable=False),
    sa.Column('phone', sa.String(length=32), nullable=True),
    sa.Column('city', sa.String(length=80), nullable=True),
    sa.Column('joined_date', sa.Date(), nullable=True),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('user_id')
    )
    op.create_table('books',
    sa.Column('id', sa.String(length=16), nullable=False),
    sa.Column('author_id', sa.String(length=16), nullable=False),
    sa.Column('title', sa.String(length=255), nullable=False),
    sa.Column('isbn', sa.String(length=32), nullable=True),
    sa.Column('genre', sa.String(length=120), nullable=True),
    sa.Column('publication_date', sa.Date(), nullable=True),
    sa.Column('status', sa.String(length=80), nullable=False),
    sa.Column('mrp', sa.Numeric(precision=10, scale=2), nullable=True),
    sa.Column('royalty_per_copy', sa.Numeric(precision=10, scale=2), nullable=True),
    sa.Column('copies_sold', sa.Integer(), nullable=False),
    sa.Column('royalty_earned', sa.Numeric(precision=12, scale=2), nullable=False),
    sa.Column('royalty_paid', sa.Numeric(precision=12, scale=2), nullable=False),
    sa.Column('royalty_pending', sa.Numeric(precision=12, scale=2), nullable=False),
    sa.Column('last_payout_date', sa.Date(), nullable=True),
    sa.Column('print_partner', sa.String(length=80), nullable=True),
    sa.Column('available_on', sa.JSON(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['author_id'], ['author_profiles.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_books_author_id'), 'books', ['author_id'], unique=False)
    op.create_table('tickets',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('number', sa.Integer(), server_default=sa.text("nextval('ticket_number_seq')"), nullable=False),
    sa.Column('author_id', sa.String(length=16), nullable=False),
    sa.Column('book_id', sa.String(length=16), nullable=True),
    sa.Column('subject', sa.String(length=200), nullable=False),
    sa.Column('description', sa.Text(), nullable=False),
    sa.Column('status', sa.String(length=16), nullable=False),
    sa.Column('category', sa.String(length=32), nullable=False),
    sa.Column('priority', sa.String(length=16), nullable=False),
    sa.Column('ai_category', sa.String(length=32), nullable=True),
    sa.Column('ai_priority', sa.String(length=16), nullable=True),
    sa.Column('ai_confidence', sa.Float(), nullable=True),
    sa.Column('ai_reasoning', sa.Text(), nullable=True),
    sa.Column('ai_status', sa.String(length=16), nullable=False),
    sa.Column('category_overridden', sa.Boolean(), nullable=False),
    sa.Column('priority_overridden', sa.Boolean(), nullable=False),
    sa.Column('ai_draft', sa.Text(), nullable=True),
    sa.Column('ai_draft_generated_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('assigned_to_id', sa.Uuid(), nullable=True),
    sa.Column('resolved_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('last_activity_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['assigned_to_id'], ['users.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['author_id'], ['author_profiles.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['book_id'], ['books.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('number')
    )
    op.create_index(op.f('ix_tickets_author_id'), 'tickets', ['author_id'], unique=False)
    op.create_index(op.f('ix_tickets_category'), 'tickets', ['category'], unique=False)
    op.create_index(op.f('ix_tickets_priority'), 'tickets', ['priority'], unique=False)
    op.create_index(op.f('ix_tickets_status'), 'tickets', ['status'], unique=False)
    op.create_table('ai_calls',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('ticket_id', sa.Uuid(), nullable=True),
    sa.Column('purpose', sa.String(length=16), nullable=False),
    sa.Column('model', sa.String(length=80), nullable=False),
    sa.Column('status', sa.String(length=16), nullable=False),
    sa.Column('input_tokens', sa.Integer(), nullable=False),
    sa.Column('output_tokens', sa.Integer(), nullable=False),
    sa.Column('cache_read_tokens', sa.Integer(), nullable=False),
    sa.Column('cache_write_tokens', sa.Integer(), nullable=False),
    sa.Column('latency_ms', sa.Integer(), nullable=False),
    sa.Column('error', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['ticket_id'], ['tickets.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_ai_calls_ticket_id'), 'ai_calls', ['ticket_id'], unique=False)
    op.create_table('attachments',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('ticket_id', sa.Uuid(), nullable=False),
    sa.Column('filename', sa.String(length=255), nullable=False),
    sa.Column('mime_type', sa.String(length=120), nullable=True),
    sa.Column('size_bytes', sa.Integer(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['ticket_id'], ['tickets.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_attachments_ticket_id'), 'attachments', ['ticket_id'], unique=False)
    op.create_table('ticket_messages',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('ticket_id', sa.Uuid(), nullable=False),
    sa.Column('sender_id', sa.Uuid(), nullable=True),
    sa.Column('kind', sa.String(length=16), nullable=False),
    sa.Column('body', sa.Text(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['sender_id'], ['users.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['ticket_id'], ['tickets.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_ticket_messages_ticket_id'), 'ticket_messages', ['ticket_id'], unique=False)
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_index(op.f('ix_ticket_messages_ticket_id'), table_name='ticket_messages')
    op.drop_table('ticket_messages')
    op.drop_index(op.f('ix_attachments_ticket_id'), table_name='attachments')
    op.drop_table('attachments')
    op.drop_index(op.f('ix_ai_calls_ticket_id'), table_name='ai_calls')
    op.drop_table('ai_calls')
    op.drop_index(op.f('ix_tickets_status'), table_name='tickets')
    op.drop_index(op.f('ix_tickets_priority'), table_name='tickets')
    op.drop_index(op.f('ix_tickets_category'), table_name='tickets')
    op.drop_index(op.f('ix_tickets_author_id'), table_name='tickets')
    op.drop_table('tickets')
    op.drop_index(op.f('ix_books_author_id'), table_name='books')
    op.drop_table('books')
    op.drop_table('author_profiles')
    op.drop_index(op.f('ix_users_email'), table_name='users')
    op.drop_table('users')
    op.execute(sa.schema.DropSequence(sa.Sequence('ticket_number_seq')))
    # ### end Alembic commands ###
