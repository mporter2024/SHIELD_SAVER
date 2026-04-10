from flask import Blueprint, request, jsonify, session
from models.database import get_db
import sqlite3

agenda_bp = Blueprint("agenda", __name__)


def _owns_event(db, event_id, user_id):
    row = db.execute("SELECT id FROM events WHERE id = ? AND user_id = ?", (event_id, user_id)).fetchone()
    return row is not None


def _owns_agenda_item(db, agenda_item_id, user_id):
    row = db.execute(
        """
        SELECT agenda_items.id
        FROM agenda_items
        INNER JOIN events ON agenda_items.event_id = events.id
        WHERE agenda_items.id = ? AND events.user_id = ?
        """,
        (agenda_item_id, user_id),
    ).fetchone()
    return row is not None


@agenda_bp.get('/event/<int:event_id>')
def get_event_agenda(event_id):
    if 'user_id' not in session:
        return jsonify({'error': 'Not logged in'}), 401

    db = get_db()
    if not _owns_event(db, event_id, session['user_id']):
        return jsonify({'error': 'Event not found'}), 404

    agenda_rows = db.execute(
        """
        SELECT *
        FROM agenda_items
        WHERE event_id = ?
        ORDER BY COALESCE(agenda_date, ''), COALESCE(start_time, end_time, title), id ASC
        """,
        (event_id,),
    ).fetchall()

    agenda = []
    for row in agenda_rows:
        item = dict(row)
        lineups = db.execute(
            'SELECT * FROM lineup_items WHERE agenda_item_id = ? ORDER BY id ASC',
            (row['id'],),
        ).fetchall()
        item['lineup'] = [dict(line) for line in lineups]
        agenda.append(item)

    return jsonify(agenda), 200


@agenda_bp.post('/items')
def create_agenda_item():
    if 'user_id' not in session:
        return jsonify({'error': 'Not logged in'}), 401

    db = get_db()
    data = request.get_json(silent=True) or {}
    event_id = data.get('event_id')
    title = (data.get('title') or '').strip()
    description = (data.get('description') or '').strip() or None
    agenda_date = data.get('agenda_date') or None
    start_time = data.get('start_time') or None
    end_time = data.get('end_time') or None

    if not event_id or not title:
        return jsonify({'error': 'event_id and title are required'}), 400

    try:
        event_id = int(event_id)
    except (TypeError, ValueError):
        return jsonify({'error': 'event_id must be an integer'}), 400

    if not _owns_event(db, event_id, session['user_id']):
        return jsonify({'error': 'Event not found'}), 404

    try:
        cursor = db.execute(
            """
            INSERT INTO agenda_items (event_id, title, description, agenda_date, start_time, end_time)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (event_id, title, description, agenda_date, start_time, end_time),
        )
        db.commit()
    except sqlite3.IntegrityError as e:
        return jsonify({'error': 'Database constraint failed', 'details': str(e)}), 400

    created = db.execute('SELECT * FROM agenda_items WHERE id = ?', (cursor.lastrowid,)).fetchone()
    item = dict(created)
    item['lineup'] = []
    return jsonify(item), 201


@agenda_bp.put('/items/<int:agenda_item_id>')
def update_agenda_item(agenda_item_id):
    if 'user_id' not in session:
        return jsonify({'error': 'Not logged in'}), 401

    db = get_db()
    if not _owns_agenda_item(db, agenda_item_id, session['user_id']):
        return jsonify({'error': 'Agenda item not found'}), 404

    data = request.get_json(silent=True) or {}
    title = (data.get('title') or '').strip() if 'title' in data else None
    description = data.get('description') if 'description' in data else None
    agenda_date = data.get('agenda_date') if 'agenda_date' in data else None
    start_time = data.get('start_time') if 'start_time' in data else None
    end_time = data.get('end_time') if 'end_time' in data else None

    db.execute(
        """
        UPDATE agenda_items
        SET title = COALESCE(?, title),
            description = COALESCE(?, description),
            agenda_date = COALESCE(?, agenda_date),
            start_time = COALESCE(?, start_time),
            end_time = COALESCE(?, end_time)
        WHERE id = ?
        """,
        (title, description, agenda_date, start_time, end_time, agenda_item_id),
    )
    db.commit()

    updated = db.execute('SELECT * FROM agenda_items WHERE id = ?', (agenda_item_id,)).fetchone()
    item = dict(updated)
    lines = db.execute('SELECT * FROM lineup_items WHERE agenda_item_id = ? ORDER BY id ASC', (agenda_item_id,)).fetchall()
    item['lineup'] = [dict(line) for line in lines]
    return jsonify(item), 200


@agenda_bp.delete('/items/<int:agenda_item_id>')
def delete_agenda_item(agenda_item_id):
    if 'user_id' not in session:
        return jsonify({'error': 'Not logged in'}), 401

    db = get_db()
    if not _owns_agenda_item(db, agenda_item_id, session['user_id']):
        return jsonify({'error': 'Agenda item not found'}), 404

    db.execute('DELETE FROM lineup_items WHERE agenda_item_id = ?', (agenda_item_id,))
    db.execute('DELETE FROM agenda_items WHERE id = ?', (agenda_item_id,))
    db.commit()
    return jsonify({'message': 'Agenda item deleted successfully'}), 200


@agenda_bp.post('/lineup')
def create_lineup_item():
    if 'user_id' not in session:
        return jsonify({'error': 'Not logged in'}), 401

    db = get_db()
    data = request.get_json(silent=True) or {}
    agenda_item_id = data.get('agenda_item_id')
    name = (data.get('name') or '').strip()
    role = (data.get('role') or '').strip() or None

    if not agenda_item_id or not name:
        return jsonify({'error': 'agenda_item_id and name are required'}), 400

    try:
        agenda_item_id = int(agenda_item_id)
    except (TypeError, ValueError):
        return jsonify({'error': 'agenda_item_id must be an integer'}), 400

    if not _owns_agenda_item(db, agenda_item_id, session['user_id']):
        return jsonify({'error': 'Agenda item not found'}), 404

    try:
        cursor = db.execute(
            'INSERT INTO lineup_items (agenda_item_id, name, role) VALUES (?, ?, ?)',
            (agenda_item_id, name, role),
        )
        db.commit()
    except sqlite3.IntegrityError as e:
        return jsonify({'error': 'Database constraint failed', 'details': str(e)}), 400

    created = db.execute('SELECT * FROM lineup_items WHERE id = ?', (cursor.lastrowid,)).fetchone()
    return jsonify(dict(created)), 201


@agenda_bp.delete('/lineup/<int:lineup_item_id>')
def delete_lineup_item(lineup_item_id):
    if 'user_id' not in session:
        return jsonify({'error': 'Not logged in'}), 401

    db = get_db()
    row = db.execute(
        """
        SELECT lineup_items.id
        FROM lineup_items
        INNER JOIN agenda_items ON lineup_items.agenda_item_id = agenda_items.id
        INNER JOIN events ON agenda_items.event_id = events.id
        WHERE lineup_items.id = ? AND events.user_id = ?
        """,
        (lineup_item_id, session['user_id']),
    ).fetchone()

    if row is None:
        return jsonify({'error': 'Lineup item not found'}), 404

    db.execute('DELETE FROM lineup_items WHERE id = ?', (lineup_item_id,))
    db.commit()
    return jsonify({'message': 'Lineup item deleted successfully'}), 200
