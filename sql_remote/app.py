from flask import Flask, request, render_template, jsonify, redirect, url_for, session
import psycopg2
import os
from flask import render_template_string
import tempfile

app = Flask(__name__)
app.secret_key = 'tu_clave_secreta'  # Necesaria para usar sesiones

# Configuración de la conexión a PostgreSQL
DB_HOST = "127.0.0.1"
DB_NAME = "g5ix"
DB_USER = "postgres"
DB_PASS = "postavalon"

def get_db_connection():
    conn = psycopg2.connect(host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASS)
    return conn

@app.route('/', methods=['GET'])
def index():
    try:
        # Conectar a la base de datos
        conn = get_db_connection()
        cur = conn.cursor()

        # Obtener el listado de tablas
        cur.execute("SELECT table_name FROM information_schema.tables WHERE table_schema='public'")
        tables = cur.fetchall()

        # Obtener relaciones de claves foráneas
        cur.execute("""
        SELECT
            tc.table_name,
            kcu.column_name,
            ccu.table_name AS foreign_table_name
        FROM
            information_schema.table_constraints AS tc
            JOIN information_schema.key_column_usage AS kcu
              ON tc.constraint_schema = kcu.constraint_schema
              AND tc.table_name = kcu.table_name
              AND tc.constraint_name = kcu.constraint_name
            JOIN information_schema.constraint_column_usage AS ccu
              ON ccu.constraint_schema = tc.constraint_schema
              AND ccu.constraint_name = tc.constraint_name
        WHERE tc.constraint_type = 'FOREIGN KEY'
        """)
        relationships = cur.fetchall()

        # Estructura para el esquema
        schema = {}
        for table in tables:
            schema[table[0]] = {'columns': [], 'foreign_keys': []}

        for table, column, foreign_table in relationships:
            if table in schema:
                schema[table]['foreign_keys'].append(foreign_table)

        for table in tables:
            cur.execute(f"SELECT column_name FROM information_schema.columns WHERE table_name='{table[0]}'")
            columns = cur.fetchall()
            schema[table[0]]['columns'] = [col[0] for col in columns]

        # Cerrar la conexión
        cur.close()
        conn.close()

        return render_template('index.html', schema=schema)
    
    except Exception as e:
        return str(e)

@app.route('/query', methods=['POST'])
def query():
    try:
        sql_query = request.form.get('query')
        if not sql_query:
            return redirect(url_for('index'))

        # Conectar a la base de datos y ejecutar la consulta
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(sql_query)

        # Obtener los resultados de la consulta
        results = cur.fetchall()
        column_names = [desc[0] for desc in cur.description]

        # Guardar los resultados en una sesión temporal
        with tempfile.NamedTemporaryFile(delete=False, suffix='.html') as tmpfile:
            file_path = tmpfile.name
            table_html = render_template_string('''
            <!DOCTYPE html>
            <html>
            <head>
                <title>Resultados de la consulta</title>
            </head>
            <body>
                <table border="1">
                    <thead>
                        <tr>
                            {% for column in column_names %}
                            <th>{{ column }}</th>
                            {% endfor %}
                        </tr>
                    </thead>
                    <tbody>
                        {% for row in results %}
                        <tr>
                            {% for cell in row %}
                            <td>{{ cell }}</td>
                            {% endfor %}
                        </tr>
                        {% endfor %}
                    </tbody>
                </table>
            </body>
            </html>
            ''', column_names=column_names, results=results)
            tmpfile.write(table_html.encode('utf-8'))

        # Guardar la ruta del archivo en la sesión
        session['results_file'] = file_path

        # Redirigir a la nueva ruta
        return redirect(url_for('show_results'))
    
    except Exception as e:
        return str(e)

@app.route('/results', methods=['GET'])
def show_results():
    file_path = session.get('results_file')
    if not file_path or not os.path.exists(file_path):
        return "No se encontraron resultados"

    # Enviar el archivo HTML al navegador
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # Borrar el archivo después de enviarlo
    os.remove(file_path)
    return content

@app.route('/api/schema', methods=['GET'])
def get_schema():
    try:
        # Conectar a la base de datos
        conn = get_db_connection()
        cur = conn.cursor()

        # Obtener el listado de tablas y sus relaciones
        cur.execute("""
        SELECT
            tc.table_name,
            kcu.column_name,
            ccu.table_name AS foreign_table_name
        FROM
            information_schema.table_constraints AS tc
            JOIN information_schema.key_column_usage AS kcu
              ON tc.constraint_schema = kcu.constraint_schema
              AND tc.table_name = kcu.table_name
              AND tc.constraint_name = kcu.constraint_name
            JOIN information_schema.constraint_column_usage AS ccu
              ON ccu.constraint_schema = tc.constraint_schema
              AND ccu.constraint_name = tc.constraint_name
        WHERE tc.constraint_type = 'FOREIGN KEY'
        """)
        relationships = cur.fetchall()

        # Obtener el listado de tablas
        cur.execute("SELECT table_name FROM information_schema.tables WHERE table_schema='public'")
        tables = cur.fetchall()

        # Estructura de datos para el árbol
        schema = {}
        for table in tables:
            schema[table[0]] = {'columns': [], 'foreign_keys': []}

        for table, column, foreign_table in relationships:
            if table in schema:
                schema[table]['foreign_keys'].append(foreign_table)

        for table in tables:
            cur.execute(f"SELECT column_name FROM information_schema.columns WHERE table_name='{table[0]}'")
            columns = cur.fetchall()
            schema[table[0]]['columns'] = [col[0] for col in columns]

        # Cerrar la conexión
        cur.close()
        conn.close()

        # Devolver el esquema en formato JSON
        return jsonify(schema)
    
    except Exception as e:
        return str(e), 500

if __name__ == '__main__':
    app.run(debug=True)