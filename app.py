from flask import Flask, render_template, request, jsonify, session, send_file
import os, hashlib, pg8000.dbapi, ssl, io, json
from urllib.parse import urlparse, unquote
from datetime import datetime, timedelta

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY','yse-quotation-2026-secret')
app.permanent_session_lifetime = timedelta(days=90)

SHEET_ID = '1kaj47J30H2GiGOu7undGI9dGY_c6LvQ1cK5K8-LurD8'
COMPANY_NAME   = 'Yuvaraj Scaffolding Trader Pvt Ltd'
COMPANY_SHORT  = 'YSE – Yuvaraj Scaffolding Trader Pvt Ltd'
COMPANY_ADDR   = 'Harvey Nagar 4th Street, Arasaridi, Madurai – 625016'
COMPANY_GST    = 'GST No: 33AACCY0928N1Z3'
CGST_RATE      = 0.09
SGST_RATE      = 0.09

EMPLOYEE_SEALS = {
    'dharani':         'seal_dharani.png',
    'abinaya':         'seal_abinaya.png',
    'venkadavarshini': 'seal_venkadavarshini.png',
    'mutheeswari':     'seal_mutheeswari.png',
}
EMPLOYEE_DESIGNATIONS = {
    'dharani':         'Sales Executive',
    'abinaya':         'Sales Executive',
    'venkadavarshini': 'Sales Executive',
    'mutheeswari':     'Sales Executive',
    'yuvaraj':         'Managing Director',
    'ramya':           'Sales Executive',
}
TERMS_AND_CONDITIONS = [
    "All prices are inclusive of GST at 18% (CGST 9% + SGST 9%) unless mentioned otherwise.",
    "For bank quotation,100% Advance Payment is required from customer/Bank for booking sale orders.",
    "For normal quotation,50% advance payment is required from customer for booking sale order.",
    "Material once sold will not be taken back without prior written approval.",
    "75% advance payment required for customized order.",
    "Balance payment should be made against invoice before dispatch of products.",
    "Payment mode should be made through bank.",
    "Quotation rates shall remain 15days.",
    "Loading charges are to be borne by the customer.",
    "Machine printing / initial charges are non-refundable.",
]
BANK_DETAILS = {
    'account_name': COMPANY_NAME.upper(),
    'bank_name':    'UCO BANK',
    'account_no':   '11770210002018',
    'ifsc_code':    'ucba0001177',
    'branch':       'KK Nagar',
    'account_type': 'Current Account',
}

# ── HELPERS ──
def hash_password(p): return hashlib.sha256((p+'yse2026salt').encode()).hexdigest()
def verify_password(p,h): return hash_password(p)==h

_db_pool = None

def get_db():
    global _db_pool
    if _db_pool is None or _db_pool.in_transaction:
        db_url=os.environ.get('DATABASE_URL','')
        if db_url.startswith('postgres://'): db_url=db_url.replace('postgres://','postgresql://',1)
        p=urlparse(db_url)
        ssl_ctx=ssl.create_default_context(); ssl_ctx.check_hostname=False; ssl_ctx.verify_mode=ssl.CERT_NONE
        try:
            _db_pool=pg8000.dbapi.connect(user=unquote(p.username),password=unquote(p.password),
                host=p.hostname,port=p.port or 5432,database=p.path.lstrip('/'),ssl_context=ssl_ctx,
                timeout=10)
        except: _db_pool=None; raise
    return _db_pool

def query(sql,params=None):
    con=get_db()
    try:
        cur=con.cursor(); cur.execute(sql,params or [])
        cols=[d[0] for d in cur.description] if cur.description else []
        rows=cur.fetchall() if cur.description else []
        con.commit(); return [dict(zip(cols,r)) for r in rows]
    finally: con.close()

def execute(sql,params=None):
    con=get_db()
    try:
        cur=con.cursor(); cur.execute(sql,params or [])
        result=cur.fetchall() if cur.description else []
        con.commit(); return result
    finally: con.close()

def init_db():
    execute("""CREATE TABLE IF NOT EXISTS yse_users(
        id SERIAL PRIMARY KEY,email TEXT UNIQUE NOT NULL,name TEXT NOT NULL,
        password_hash TEXT NOT NULL DEFAULT '',role TEXT DEFAULT 'employee',
        contact_name TEXT DEFAULT '',contact_phone TEXT DEFAULT '',
        designation TEXT DEFAULT 'Sales Executive',created_at TIMESTAMP DEFAULT NOW())""")
    for col in ["contact_name TEXT DEFAULT ''","contact_phone TEXT DEFAULT ''","designation TEXT DEFAULT 'Sales Executive'"]:
        try: execute(f"ALTER TABLE yse_users ADD COLUMN IF NOT EXISTS {col}")
        except: pass

    execute("""CREATE TABLE IF NOT EXISTS yse_products(
        id SERIAL PRIMARY KEY,name TEXT NOT NULL,product_type TEXT DEFAULT '',
        size TEXT DEFAULT '',specification TEXT DEFAULT '',
        default_rate REAL DEFAULT 0,default_weight REAL DEFAULT 0,
        calc_type TEXT DEFAULT 'A',loading_rate REAL DEFAULT 150,
        is_initial BOOLEAN DEFAULT FALSE,active BOOLEAN DEFAULT TRUE)""")
    for col in ["size TEXT DEFAULT ''","specification TEXT DEFAULT ''",
                "loading_rate REAL DEFAULT 150","product_type TEXT DEFAULT ''",
                "is_initial BOOLEAN DEFAULT FALSE",
                "unit TEXT DEFAULT 'Nos'","pieces_per_unit INTEGER DEFAULT 1"]:
        try: execute(f"ALTER TABLE yse_products ADD COLUMN IF NOT EXISTS {col}")
        except: pass

    execute("CREATE TABLE IF NOT EXISTS yse_settings(key TEXT PRIMARY KEY,value TEXT)")
    execute("""CREATE TABLE IF NOT EXISTS yse_quotations(
        id SERIAL PRIMARY KEY,quot_no TEXT NOT NULL,
        customer_name TEXT NOT NULL,customer_location TEXT NOT NULL,
        customer_phone TEXT NOT NULL,items JSONB NOT NULL,
        loading_charges REAL DEFAULT 0,initial_charges REAL DEFAULT 0,
        taxable_subtotal REAL DEFAULT 0,cgst_amount REAL DEFAULT 0,
        sgst_amount REAL DEFAULT 0,grand_total REAL DEFAULT 0,
        total_weight REAL DEFAULT 0,created_by INTEGER,
        contact_person TEXT DEFAULT '',contact_phone TEXT DEFAULT '',
        created_at TIMESTAMP DEFAULT NOW())""")
    for col in ["initial_charges REAL DEFAULT 0","taxable_subtotal REAL DEFAULT 0",
                "cgst_amount REAL DEFAULT 0","sgst_amount REAL DEFAULT 0"]:
        try: execute(f"ALTER TABLE yse_quotations ADD COLUMN IF NOT EXISTS {col}")
        except: pass

    for k,v in {'quot_prefix':'YSE/QT','quot_counter':'100'}.items():
        execute("INSERT INTO yse_settings(key,value) VALUES(%s,%s) ON CONFLICT DO NOTHING",[k,v])

    # Default products — Type B loading_rate = 0.15 Rs/kg (NOT per 1000kg)
    # Machine Print / Initial is NOT in product list — handled separately in quotation
    defaults=[
        # name,ptype,size,spec,rate,wt,ctype,lrate,is_init,unit,ppu
        ('Cuplock','Scaffolding','2000mm','Heavy Duty M.S. Scaffolding Cuplock System',110,10,'B',0.15,False,'Nos',1),
        ('Cuplock','Scaffolding','3000mm','Heavy Duty M.S. Scaffolding Cuplock System',110,15,'B',0.15,False,'Nos',1),
        ('Ledger','Scaffolding','2000mm','M.S. Ledger for Cuplock Scaffolding',110,6.5,'B',0.15,False,'Nos',1),
        ('Ledger','Scaffolding','1200mm','M.S. Ledger for Cuplock Scaffolding',110,4,'B',0.15,False,'Nos',1),
        ('Centring Sheet','Special Type','2129x457mm','14 Gauge 2mm Hot Rolled M.S. Sheet',100,0,'A',0,False,'Nos',1),
        ('Centring Sheet','Regular Type','2129x457mm','12 Gauge Hot Rolled M.S. Sheet',90,0,'A',0,False,'Nos',1),
        ('Centring Sheet','Angle Type','2129x457mm','Angle M.S. Sheet',85,0,'A',0,False,'Nos',1),
        ('Earth Beam Sheet','Special Type','Standard','Hot Rolled M.S. Sheet – Special',100,8,'B',0.15,False,'Nos',1),
        ('Earth Beam Sheet','Regular Type','Standard','Hot Rolled M.S. Sheet – Regular',90,8,'B',0.15,False,'Nos',1),
        ('Earth Beam Sheet','Angle Type','Standard','Angle M.S. Sheet',85,8,'B',0.15,False,'Nos',1),
        ('Column Box','L Type','Standard','M.S. Column Box L Type – 1 Set = 2 Pieces',110,8,'B',0.15,False,'Set',2),
        ('Column Box','Single Type','Standard','M.S. Column Box Single Type',110,4,'B',0.15,False,'Nos',1),
        ('Jockey','Adjustable Type','Standard','M.S. Adjustable Jockey',150,0,'A',0,False,'Nos',1),
        ('Span','Scaffolding','Standard','M.S. Span / Runner',120,0,'A',0,False,'Nos',1),
        ('Prop','Scaffolding','3000mm','M.S. Adjustable Prop',110,8,'B',0.15,False,'Nos',1),
    ]
    for name,ptype,size,spec,rate,wt,ctype,lrate,is_init,unit,ppu in defaults:
        execute("""INSERT INTO yse_products(name,product_type,size,specification,default_rate,default_weight,calc_type,loading_rate,is_initial,unit,pieces_per_unit)
            SELECT %s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s WHERE NOT EXISTS(
                SELECT 1 FROM yse_products WHERE name=%s AND (size=%s OR size=''))""",
            [name,ptype,size,spec,rate,wt,ctype,lrate,is_init,unit,ppu,name,size])

@app.before_request
def ensure_db():
    app._db_ready=True

def append_to_sheet(quot_no,date_str,cname,cphone,cloc,grand_total,emp_name):
    try:
        import gspread
        from google.oauth2.service_account import Credentials
        SA=os.path.join(os.path.dirname(__file__),'service_account.json')
        if not os.path.exists(SA): return
        creds=Credentials.from_service_account_file(SA,scopes=['https://spreadsheets.google.com/feeds','https://www.googleapis.com/auth/drive'])
        ws=gspread.authorize(creds).open_by_key(SHEET_ID).sheet1
        if ws.row_count==0 or ws.cell(1,1).value!='S.NO':
            ws.clear()
            ws.append_row(['S.NO','Quotation No','Date','Customer Name','Phone','Address','Total','Reference'])
        ws.append_row([len(ws.get_all_values()),quot_no,date_str,cname,cphone,cloc,f"Rs.{int(grand_total):,}",emp_name])
    except Exception as e: print(f"Sheet: {e}")

# ── AUTH ──
@app.route('/')
def index(): return render_template('index.html')

@app.route('/api/migrate')
def migrate():
    """Run once to add new columns to existing Supabase DB"""
    results = []
    migrations = [
        "ALTER TABLE yse_products ADD COLUMN IF NOT EXISTS unit TEXT DEFAULT 'Nos'",
        "ALTER TABLE yse_products ADD COLUMN IF NOT EXISTS pieces_per_unit INTEGER DEFAULT 1",
        "UPDATE yse_products SET unit='Set', pieces_per_unit=2 WHERE LOWER(name)='column box' AND LOWER(product_type) LIKE '%l type%'",
        "UPDATE yse_products SET unit='Nos', pieces_per_unit=1 WHERE unit IS NULL",
        "ALTER TABLE yse_quotations ADD COLUMN IF NOT EXISTS initial_charges REAL DEFAULT 0",
        "ALTER TABLE yse_quotations ADD COLUMN IF NOT EXISTS taxable_subtotal REAL DEFAULT 0",
        "ALTER TABLE yse_quotations ADD COLUMN IF NOT EXISTS cgst_amount REAL DEFAULT 0",
        "ALTER TABLE yse_quotations ADD COLUMN IF NOT EXISTS sgst_amount REAL DEFAULT 0",
    ]
    for sql in migrations:
        try:
            execute(sql)
            results.append(f"✅ {sql[:60]}")
        except Exception as e:
            results.append(f"⚠️ {sql[:60]} → {str(e)[:50]}")
    return jsonify({'ok': True, 'results': results})

@app.route('/api/setup')
def setup():
    try:
        for col in ["contact_name TEXT DEFAULT ''","contact_phone TEXT DEFAULT ''","designation TEXT DEFAULT 'Sales Executive'"]:
            try: execute(f"ALTER TABLE yse_users ADD COLUMN IF NOT EXISTS {col}")
            except: pass
        users=[
            ('yuva.yuvarajscaff@gmail.com','Yuvaraj','Yuvaraj1029@','admin','Yuvaraj','8012501301','Managing Director'),
            ('abinaya.yuvarajscaff@gmail.com','Abinaya','yuvaraj@123','employee','Abinaya','8012501301','Sales Executive'),
            ('dharani.yuvarajscaff@gmail.com','Dharani','Dhara@123','employee','Dharani','8925959824','Sales Executive'),
            ('venkadavarshini.yuvarajscaff@gmail.com','Venkadavarshini','yuvaraj@123','employee','Venkadavarshini','','Sales Executive'),
            ('ramya.yuvarajscaff@gmail.com','Ramya','yuvaraj@123','employee','Ramya','','Sales Executive'),
            ('mutheeswari.yuvarajscaff@gmail.com','Mutheeswari','yuvaraj@123','employee','Mutheeswari','','Sales Executive'),
        ]
        results=[]
        for email,name,pwd,role,cname,cphone,desig in users:
            if query('SELECT id FROM yse_users WHERE email=%s',[email]):
                execute('UPDATE yse_users SET password_hash=%s,role=%s,contact_name=%s,contact_phone=%s,designation=%s WHERE email=%s',
                        [hash_password(pwd),role,cname,cphone,desig,email]); results.append(f"Updated:{name}")
            else:
                execute('INSERT INTO yse_users(email,name,password_hash,role,contact_name,contact_phone,designation) VALUES(%s,%s,%s,%s,%s,%s,%s)',
                        [email,name,hash_password(pwd),role,cname,cphone,desig]); results.append(f"Created:{name}")
        return jsonify({'ok':True,'results':results})
    except Exception as e: return jsonify({'ok':False,'error':str(e)}),500

@app.route('/api/login',methods=['POST'])
def login():
    d=request.json; email=(d.get('email') or '').strip().lower(); pwd=(d.get('password') or '').strip()
    if not email or not pwd: return jsonify({'ok':False,'msg':'Please enter email and password.'}),400
    users=query('SELECT * FROM yse_users WHERE email=%s',[email])
    if not users: return jsonify({'ok':False,'msg':'Email not found. Contact admin.'}),401
    u=users[0]
    if not verify_password(pwd,u['password_hash']): return jsonify({'ok':False,'msg':'Wrong password. Try again.'}),401
    session.permanent=True
    session['user_id']=u['id']; session['user_email']=u['email']
    session['user_name']=u['name']; session['user_role']=u['role']
    return jsonify({'ok':True,'user':{'id':u['id'],'name':u['name'],'email':u['email'],'role':u['role']}})

@app.route('/api/me')
def me():
    if 'user_id' not in session: return jsonify({'ok':False}),401
    return jsonify({'ok':True,'user':{'id':session['user_id'],'name':session['user_name'],'email':session['user_email'],'role':session.get('user_role','employee')}})

@app.route('/api/logout',methods=['POST'])
def logout(): session.clear(); return jsonify({'ok':True})

@app.route('/api/change-password',methods=['POST'])
def change_password():
    if 'user_id' not in session: return jsonify({'ok':False}),401
    d=request.json; old=(d.get('old_password') or '').strip(); new=(d.get('new_password') or '').strip()
    if not old or not new: return jsonify({'ok':False,'msg':'Please fill all fields.'}),400
    users=query('SELECT * FROM yse_users WHERE id=%s',[session['user_id']])
    if not users or not verify_password(old,users[0]['password_hash']): return jsonify({'ok':False,'msg':'Current password is wrong.'}),401
    if len(new)<6: return jsonify({'ok':False,'msg':'Password must be at least 6 characters.'}),400
    execute('UPDATE yse_users SET password_hash=%s WHERE id=%s',[hash_password(new),session['user_id']])
    return jsonify({'ok':True})

@app.route('/api/profile',methods=['GET'])
def get_profile():
    if 'user_id' not in session: return jsonify({'ok':False}),401
    u=query('SELECT contact_name,contact_phone,designation FROM yse_users WHERE id=%s',[session['user_id']])
    if u: return jsonify({'ok':True,'contact_name':u[0].get('contact_name') or '','contact_phone':u[0].get('contact_phone') or '','designation':u[0].get('designation') or 'Sales Executive'})
    return jsonify({'ok':True,'contact_name':'','contact_phone':'','designation':'Sales Executive'})

@app.route('/api/profile',methods=['POST'])
def save_profile():
    if 'user_id' not in session: return jsonify({'ok':False}),401
    d=request.json
    execute('UPDATE yse_users SET contact_name=%s,contact_phone=%s,designation=%s WHERE id=%s',
            [d.get('contact_name',''),d.get('contact_phone',''),d.get('designation','Sales Executive'),session['user_id']])
    return jsonify({'ok':True})

def admin_req(): return 'user_id' in session and session.get('user_role')=='admin'

@app.route('/api/admin/employees',methods=['GET'])
def get_employees():
    if not admin_req(): return jsonify({'ok':False}),403
    return jsonify(query("SELECT id,email,name,role,contact_name,contact_phone,designation,created_at FROM yse_users ORDER BY role,name"))

@app.route('/api/admin/employees',methods=['POST'])
def add_employee():
    if not admin_req(): return jsonify({'ok':False}),403
    d=request.json; email=(d.get('email') or '').strip().lower(); name=(d.get('name') or '').strip(); pwd=(d.get('password') or '').strip(); role=d.get('role','employee')
    if not email or not name or not pwd: return jsonify({'ok':False,'msg':'All fields required.'}),400
    if query('SELECT id FROM yse_users WHERE email=%s',[email]): return jsonify({'ok':False,'msg':'Email already exists.'}),400
    execute('INSERT INTO yse_users(email,name,password_hash,role) VALUES(%s,%s,%s,%s)',[email,name,hash_password(pwd),role])
    return jsonify({'ok':True})

@app.route('/api/admin/employees/<int:uid>',methods=['DELETE'])
def delete_employee(uid):
    if not admin_req(): return jsonify({'ok':False}),403
    execute("DELETE FROM yse_users WHERE id=%s AND role!='admin'",[uid]); return jsonify({'ok':True})

@app.route('/api/admin/employees/<int:uid>/reset-password',methods=['POST'])
def reset_password(uid):
    if not admin_req(): return jsonify({'ok':False}),403
    d=request.json; pwd=(d.get('password') or '').strip()
    if not pwd: return jsonify({'ok':False,'msg':'Password required.'}),400
    execute('UPDATE yse_users SET password_hash=%s WHERE id=%s',[hash_password(pwd),uid]); return jsonify({'ok':True})

@app.route('/api/admin/quotations',methods=['GET'])
def admin_get_quotations():
    if not admin_req(): return jsonify({'ok':False}),403
    uid=request.args.get('user_id')
    sql="SELECT q.*,u.name as created_by_name FROM yse_quotations q LEFT JOIN yse_users u ON q.created_by=u.id"
    rows=query(sql+" WHERE q.created_by=%s ORDER BY q.id DESC",[uid]) if uid else query(sql+" ORDER BY q.id DESC LIMIT 200")
    return jsonify(rows)

@app.route('/api/settings',methods=['GET'])
def get_settings():
    return jsonify({r['key']:r['value'] for r in query('SELECT key,value FROM yse_settings')})

@app.route('/api/settings',methods=['POST'])
def save_settings():
    if 'user_id' not in session: return jsonify({'ok':False}),401
    for k,v in request.json.items():
        execute('INSERT INTO yse_settings(key,value) VALUES(%s,%s) ON CONFLICT(key) DO UPDATE SET value=%s',[k,v,v])
    return jsonify({'ok':True})

@app.route('/api/products',methods=['GET'])
def get_products():
    return jsonify(query('SELECT * FROM yse_products WHERE active=TRUE ORDER BY name,size'))

@app.route('/api/products',methods=['POST'])
def add_product():
    if 'user_id' not in session: return jsonify({'ok':False}),401
    d=request.json
    execute('INSERT INTO yse_products(name,product_type,size,specification,default_rate,default_weight,calc_type,loading_rate,is_initial,unit,pieces_per_unit) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)',
            [d['name'],d.get('product_type',''),d.get('size',''),d.get('specification',''),
             d.get('default_rate',0),d.get('default_weight',0),d.get('calc_type','A'),d.get('loading_rate',0),d.get('is_initial',False),
             d.get('unit','Nos'),d.get('pieces_per_unit',1)])
    return jsonify({'ok':True})

@app.route('/api/products/<int:pid>',methods=['PUT'])
def update_product(pid):
    if 'user_id' not in session: return jsonify({'ok':False}),401
    d=request.json
    execute("UPDATE yse_products SET name=%s,product_type=%s,size=%s,specification=%s,default_rate=%s,default_weight=%s,calc_type=%s,loading_rate=%s,is_initial=%s,unit=%s,pieces_per_unit=%s WHERE id=%s",
            [d['name'],d.get('product_type',''),d.get('size',''),d.get('specification',''),
             d.get('default_rate',0),d.get('default_weight',0),d.get('calc_type','A'),d.get('loading_rate',0),d.get('is_initial',False),
             d.get('unit','Nos'),d.get('pieces_per_unit',1),pid])
    return jsonify({'ok':True})

@app.route('/api/products/<int:pid>',methods=['DELETE'])
def delete_product(pid):
    if 'user_id' not in session: return jsonify({'ok':False}),401
    execute('UPDATE yse_products SET active=FALSE WHERE id=%s',[pid]); return jsonify({'ok':True})

@app.route('/api/quotations',methods=['GET'])
def get_quotations():
    if 'user_id' not in session: return jsonify({'ok':False}),401
    rows=query("SELECT q.*,u.name as created_by_name FROM yse_quotations q LEFT JOIN yse_users u ON q.created_by=u.id WHERE q.created_by=%s ORDER BY q.id DESC LIMIT 100",[session['user_id']])
    return jsonify(rows)

@app.route('/api/quotations',methods=['POST'])
def create_quotation():
    if 'user_id' not in session: return jsonify({'ok':False}),401
    d=request.json
    prefix=(query("SELECT value FROM yse_settings WHERE key='quot_prefix'") or [{'value':'YSE/QT'}])[0]['value']
    counter_row=query("SELECT value FROM yse_settings WHERE key='quot_counter'")
    counter=int(counter_row[0]['value'])+1 if counter_row else 101
    execute("UPDATE yse_settings SET value=%s WHERE key='quot_counter'",[str(counter)])
    quot_no=f"{prefix}/{counter}"
    up=query('SELECT contact_name,contact_phone FROM yse_users WHERE id=%s',[session['user_id']])
    contact_name=up[0]['contact_name'] if up else session['user_name']
    contact_phone=up[0].get('contact_phone','') if up else ''
    res=execute("""INSERT INTO yse_quotations(quot_no,customer_name,customer_location,customer_phone,
        items,loading_charges,initial_charges,taxable_subtotal,cgst_amount,sgst_amount,
        grand_total,total_weight,created_by,contact_person,contact_phone)
        VALUES(%s,%s,%s,%s,%s::jsonb,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id""",
        [quot_no,d['customer_name'],d['customer_location'],d['customer_phone'],
         json.dumps(d['items']),d['loading_charges'],d.get('initial_charges',0),
         d.get('taxable_subtotal',0),d.get('cgst_amount',0),d.get('sgst_amount',0),
         d['grand_total'],d['total_weight'],session['user_id'],contact_name,contact_phone])
    new_id=res[0][0] if res else None
    append_to_sheet(quot_no,datetime.now().strftime('%d.%m.%Y'),d['customer_name'],d['customer_phone'],d['customer_location'],d['grand_total'],session['user_name'])
    return jsonify({'ok':True,'id':new_id,'quot_no':quot_no})

@app.route('/api/quotations/<int:qid>',methods=['PUT'])
def update_quotation(qid):
    if 'user_id' not in session: return jsonify({'ok':False}),401
    d=request.json
    rows=query('SELECT quot_no FROM yse_quotations WHERE id=%s AND created_by=%s',[qid,session['user_id']])
    if not rows: return jsonify({'ok':False,'msg':'Not found'}),404
    execute("""UPDATE yse_quotations SET customer_name=%s,customer_location=%s,customer_phone=%s,
        items=%s::jsonb,loading_charges=%s,initial_charges=%s,taxable_subtotal=%s,
        cgst_amount=%s,sgst_amount=%s,grand_total=%s,total_weight=%s WHERE id=%s AND created_by=%s""",
        [d['customer_name'],d['customer_location'],d['customer_phone'],json.dumps(d['items']),
         d['loading_charges'],d.get('initial_charges',0),d.get('taxable_subtotal',0),
         d.get('cgst_amount',0),d.get('sgst_amount',0),d['grand_total'],d['total_weight'],qid,session['user_id']])
    return jsonify({'ok':True,'id':qid,'quot_no':rows[0]['quot_no']})

@app.route('/api/quotations/<int:qid>',methods=['DELETE'])
def delete_quotation(qid):
    if 'user_id' not in session: return jsonify({'ok':False}),401
    if session.get('user_role')=='admin': execute('DELETE FROM yse_quotations WHERE id=%s',[qid])
    else: execute('DELETE FROM yse_quotations WHERE id=%s AND created_by=%s',[qid,session['user_id']])
    return jsonify({'ok':True})

@app.route('/api/quotations/<int:qid>/pdf')
def download_pdf(qid):
    rows=query('SELECT q.*,u.name as emp_name,u.contact_name,u.designation FROM yse_quotations q LEFT JOIN yse_users u ON q.created_by=u.id WHERE q.id=%s',[qid])
    if not rows: return jsonify({'ok':False,'msg':'Not found'}),404
    q=rows[0]; items=q['items'] if isinstance(q['items'],list) else json.loads(q['items'])
    return send_file(generate_pdf(q,items),mimetype='application/pdf',as_attachment=False,download_name=f"{q['quot_no'].replace('/','_')}.pdf")

def get_seal_path(name):
    n=(name or '').lower().strip()
    for k,f in EMPLOYEE_SEALS.items():
        if k in n or n.startswith(k):
            p=os.path.join(os.path.dirname(__file__),'static','icons',f)
            if os.path.exists(p): return p
    return None

def get_designation(name):
    n=(name or '').lower().strip()
    for k,d in EMPLOYEE_DESIGNATIONS.items():
        if k in n or n.startswith(k): return d
    return 'Sales Executive'

def fmt_rs(n):
    x = int(round(n))
    s = str(x)
    if len(s) <= 3:
        return f"Rs.{s}"
    last3 = s[-3:]
    rest = s[:-3]
    parts = []
    while len(rest) > 2:
        parts.append(rest[-2:])
        rest = rest[:-2]
    if rest:
        parts.append(rest)
    return f"Rs.{','.join(reversed(parts))},{last3}"

def generate_pdf(q,items):
    from reportlab.lib.pagesizes import A4
    from reportlab.lib import colors
    from reportlab.lib.units import mm
    from reportlab.platypus import (Paragraph,Spacer,Table,TableStyle,
        BaseDocTemplate,Frame,PageTemplate,KeepTogether,PageBreak)
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.enums import TA_CENTER,TA_LEFT,TA_RIGHT
    from reportlab.lib.utils import ImageReader
    from reportlab.platypus import Image as RLImage
    from PIL import Image as PILImage
    import io as _io

    # ── COLORS ──
    BLUE    = colors.HexColor('#1a3c8f')
    LBLUE   = colors.HexColor('#dbeafe')
    NAVY    = colors.HexColor('#0f2557')
    WHITE   = colors.white
    BLACK   = colors.HexColor('#111827')
    GRAY    = colors.HexColor('#6b7280')
    LGRAY   = colors.HexColor('#f9fafb')
    MGRAY   = colors.HexColor('#e5e7eb')
    ALT     = colors.HexColor('#eff6ff')
    GOLD    = colors.HexColor('#d97706')
    BANKBG  = colors.HexColor('#f0f9ff')
    BANKALT = colors.HexColor('#e0f2fe')
    GREEN   = colors.HexColor('#065f46')
    GREENBG = colors.HexColor('#d1fae5')
    GREENLT = colors.HexColor('#ecfdf5')

    buf=_io.BytesIO()
    W_PAGE,H_PAGE=A4
    LM=RM=15*mm; TM=50*mm; BM=16*mm
    W=W_PAGE-LM-RM
    HEADER_H=40*mm
    LOGO_PATH=os.path.join(os.path.dirname(__file__),'static','icons','logo.png')

    # Employee info
    emp=q.get('emp_name') or q.get('contact_person') or ''
    cname=q.get('contact_name') or emp
    display=cname or emp
    seal=get_seal_path(emp or display)
    desig=q.get('designation') or get_designation(emp or display)
    contact_person=q.get('contact_person') or display or ''
    contact_ph=q.get('contact_phone') or ''

    def date_str():
        ca=q.get('created_at')
        if not ca: return ''
        try: return ca.strftime('%d.%m.%Y')
        except:
            try:
                from datetime import datetime as _dt
                return _dt.fromisoformat(str(ca)[:19]).strftime('%d.%m.%Y')
            except: return str(ca)[:10]
    ds=date_str()

    # ── HEADER & FOOTER on every page ──
    # Zones (top→bottom): TOP_STRIPE | LOGO_BAND | GOLD_LINE | TITLE_BAND | CONTACT_BAND
    _TS  = 6*mm   # top navy stripe
    _LB  = 24*mm  # logo+company band
    _TB  = 9*mm   # "QUOTATION" title band
    _CB  = 8*mm   # contact strip
    TM   = _TS+_LB+1*mm+_TB+_CB+2*mm  # recalc top margin so frame starts below header

    STRIPE_Y  = H_PAGE - _TS                     # bottom y of top stripe
    LOGO_Y    = STRIPE_Y - _LB                   # bottom y of logo band
    GOLD_Y    = LOGO_Y - 1*mm                    # gold divider line y
    TITLE_Y   = GOLD_Y - _TB                     # bottom y of title band
    CONTACT_Y = TITLE_Y - _CB                    # bottom y of contact strip

    def draw_header_footer(c,doc):
        c.saveState()

        # Navy top stripe
        c.setFillColor(NAVY); c.rect(0, STRIPE_Y, W_PAGE, _TS, fill=1, stroke=0)

        # White logo band
        c.setFillColor(WHITE); c.rect(0, LOGO_Y, W_PAGE, _LB, fill=1, stroke=0)
        # Blue left accent
        c.setFillColor(BLUE);  c.rect(0, LOGO_Y, 5*mm, _LB, fill=1, stroke=0)

        # Logo — fixed in left of band, kept inside band boundaries
        LOGO_SZ = min(18*mm, _LB - 4*mm)
        logo_x  = LM + 6*mm
        logo_y  = LOGO_Y + (_LB - LOGO_SZ) / 2   # vertically centred
        text_x  = logo_x + LOGO_SZ + 5*mm

        if os.path.exists(LOGO_PATH):
            try:
                orig = PILImage.open(LOGO_PATH).convert('RGBA')
                c.drawImage(ImageReader(orig), logo_x, logo_y,
                            width=LOGO_SZ, height=LOGO_SZ,
                            preserveAspectRatio=True, mask='auto')
            except:
                text_x = LM + 8*mm
        else:
            text_x = LM + 8*mm

        # Company text — 3 lines centred in logo band
        band_cy = LOGO_Y + _LB/2
        c.setFillColor(NAVY); c.setFont('Helvetica-Bold', 11)
        c.drawString(text_x, band_cy + 5.5*mm, COMPANY_NAME.upper())
        c.setFont('Helvetica', 7.5); c.setFillColor(GRAY)
        c.drawString(text_x, band_cy + 1.5*mm, 'Manufacturer & Supplier of Scaffolding Systems | Madurai, Tamil Nadu')
        c.setFont('Helvetica-Bold', 8); c.setFillColor(BLUE)
        c.drawString(text_x, band_cy - 3*mm, COMPANY_GST)

        # Gold divider — full width, sits between logo band and title band
        c.setStrokeColor(GOLD); c.setLineWidth(2)
        c.line(0, GOLD_Y, W_PAGE, GOLD_Y)

        # White title band
        c.setFillColor(WHITE); c.rect(0, TITLE_Y, W_PAGE, _TB, fill=1, stroke=0)
        c.setFillColor(BLUE); c.setFont('Helvetica-Bold', 13)
        c.drawCentredString(W_PAGE/2, TITLE_Y + 2*mm, 'QUOTATION')
        c.setFont('Helvetica', 8); c.setFillColor(NAVY)
        c.drawString(LM, TITLE_Y + 2*mm, f"Date: {ds}")
        c.drawRightString(W_PAGE-RM, TITLE_Y + 2*mm, f"Ref No: {q['quot_no']}")

        # Light blue contact strip
        c.setFillColor(LBLUE); c.rect(0, CONTACT_Y, W_PAGE, _CB, fill=1, stroke=0)
        c.setFillColor(BLUE); c.setFont('Helvetica-Bold', 9)
        c.drawCentredString(W_PAGE/2, CONTACT_Y + 2*mm,
                            f"Contact: {contact_person}   |   Ph: {contact_ph}")

        # Footer
        c.setFillColor(NAVY); c.rect(0, 0, W_PAGE, BM-4*mm, fill=1, stroke=0)
        c.setFillColor(WHITE); c.setFont('Helvetica', 7)
        c.drawCentredString(W_PAGE/2, 5*mm,
                            f"{COMPANY_NAME}  |  {COMPANY_ADDR}  |  {COMPANY_GST}")
        c.restoreState()

    _TM=_TS+_LB+1*mm+_TB+_CB+3*mm
    doc=BaseDocTemplate(buf,pagesize=A4,leftMargin=LM,rightMargin=RM,topMargin=_TM,bottomMargin=BM)
    frame=Frame(LM,BM,W,H_PAGE-_TM-BM,id='main')
    doc.addPageTemplates([PageTemplate(id='all',frames=frame,onPage=draw_header_footer)])

    story=[]
    def ps(n,**kw): return ParagraphStyle(n,**kw)

    # Style definitions
    wh   = ps('wh', fontName='Helvetica-Bold', fontSize=8.5, textColor=WHITE, alignment=TA_CENTER)
    whl  = ps('whl',fontName='Helvetica-Bold', fontSize=8.5, textColor=WHITE)
    whr  = ps('whr',fontName='Helvetica-Bold', fontSize=8.5, textColor=WHITE, alignment=TA_RIGHT)
    bold = ps('bold',fontName='Helvetica-Bold',fontSize=10,  textColor=NAVY)
    reg  = ps('reg', fontName='Helvetica',     fontSize=9,   textColor=BLACK, leading=14)
    lbl  = ps('lbl', fontName='Helvetica-Bold',fontSize=8,   textColor=GRAY)
    val  = ps('val', fontName='Helvetica-Bold',fontSize=9,   textColor=NAVY)
    ths  = ps('ths', fontName='Helvetica-Bold',fontSize=8,   textColor=WHITE, alignment=TA_CENTER)
    tcs  = ps('tcs', fontName='Helvetica',     fontSize=8.5, textColor=BLACK, alignment=TA_CENTER)
    tls  = ps('tls', fontName='Helvetica',     fontSize=8.5, textColor=BLACK, alignment=TA_LEFT)
    tss  = ps('tss', fontName='Helvetica-Oblique',fontSize=6.5,textColor=GRAY,alignment=TA_LEFT)
    trs  = ps('trs', fontName='Helvetica',     fontSize=8.5, textColor=BLACK, alignment=TA_RIGHT)
    trb  = ps('trb', fontName='Helvetica-Bold',fontSize=9,   textColor=NAVY,  alignment=TA_RIGHT)
    gts  = ps('gts', fontName='Helvetica-Bold',fontSize=10,  textColor=WHITE, alignment=TA_RIGHT)
    smlg = ps('smlg',fontName='Helvetica-Oblique',fontSize=8,textColor=GRAY,  alignment=TA_RIGHT)
    gst_lbl=ps('gstl',fontName='Helvetica',   fontSize=8.5, textColor=BLACK,  alignment=TA_RIGHT)
    gst_val=ps('gstv',fontName='Helvetica-Bold',fontSize=8.5,textColor=GREEN, alignment=TA_RIGHT)
    gst_tot=ps('gstt',fontName='Helvetica-Bold',fontSize=11, textColor=WHITE, alignment=TA_RIGHT)

    # ── BILL TO ──
    bill=Table([
        [Paragraph('BILL TO',whl), Paragraph('QUOTATION DETAILS',whr)],
        [[Paragraph(f"<b>{q['customer_name']}</b>",bold),
          Paragraph(q['customer_location'],reg),
          Paragraph(f"Ph: {q['customer_phone']}",reg)],
         Table([[Paragraph('Date:',lbl),Paragraph(ds,val)],
                [Paragraph('Ref No:',lbl),Paragraph(q['quot_no'],val)]],
               colWidths=[W*0.12,W*0.28],
               style=TableStyle([('TOPPADDING',(0,0),(-1,-1),3),('BOTTOMPADDING',(0,0),(-1,-1),3)]))]
    ],colWidths=[W*0.55,W*0.45])
    bill.setStyle(TableStyle([
        ('BACKGROUND',(0,0),(-1,0),BLUE),('LINEBELOW',(0,0),(-1,0),2,GOLD),
        ('BACKGROUND',(0,1),(-1,1),LBLUE),
        ('TOPPADDING',(0,0),(-1,-1),7),('BOTTOMPADDING',(0,0),(-1,-1),7),
        ('LEFTPADDING',(0,0),(-1,-1),8),('RIGHTPADDING',(0,0),(-1,-1),8),
        ('ALIGN',(1,0),(1,0),'RIGHT'),('VALIGN',(0,1),(-1,1),'TOP'),
        ('BOX',(0,0),(-1,-1),1,BLUE),
    ]))
    story.append(bill); story.append(Spacer(1,5*mm))

    # ── ITEMS TABLE ──
    # Separate items: taxable vs initial/loading
    taxable_items=[it for it in items if not it.get('is_initial',False)]
    initial_items=[it for it in items if it.get('is_initial',False)]

    cw=[W*0.05,W*0.26,W*0.10,W*0.09,W*0.10,W*0.11,W*0.12,W*0.17]
    hdrs=['SI\nNO','DESCRIPTION','TYPE','SIZE','QTY','RATE\n(Rs.)','WEIGHT\n(Kg)','TOTAL\n(Rs.)']
    tdata=[[Paragraph(h,ths) for h in hdrs]]

    taxable_sub=0.0
    for i,item in enumerate(taxable_items,1):
        tot=float(item.get('total',0)); taxable_sub+=tot
        spec=item.get('specification',''); size=item.get('size',''); ptype=item.get('product_type','')
        desc=[Paragraph(str(item.get('name','')),tls)]
        if spec: desc.append(Paragraph(spec,tss))
        # Qty display — Set type shows "X Sets (Y Pcs)"
        qty_val = int(item.get('qty',0) or 0)
        unit    = item.get('unit','Nos') or 'Nos'
        ppu     = int(item.get('pieces_per_unit',1) or 1)
        if unit == 'Set' and ppu > 1:
            qty_display = f"{qty_val} Sets\n({qty_val*ppu} Pcs)"
        else:
            qty_display = f"{qty_val} {unit}"
        tdata.append([Paragraph(str(i),tcs),desc,
                      Paragraph(ptype or '-',tcs),Paragraph(size or '-',tcs),
                      Paragraph(qty_display,tcs),
                      Paragraph(fmt_rs(float(item.get('rate',0) or 0)).replace('Rs.',''),tcs),
                      Paragraph(str(item.get('weight','')) if item.get('weight') else '-',tcs),
                      Paragraph(fmt_rs(tot),trs)])

    n_rows=len(tdata)
    itbl=Table(tdata,colWidths=cw,repeatRows=1)
    itbl.setStyle(TableStyle([
        ('BACKGROUND',(0,0),(-1,0),BLUE),('LINEBELOW',(0,0),(-1,0),2,GOLD),
        *[('BACKGROUND',(0,i),(-1,i),ALT) for i in range(2,n_rows,2)],
        ('INNERGRID',(0,0),(-1,-1),0.4,MGRAY),('BOX',(0,0),(-1,-1),1,BLUE),
        ('TOPPADDING',(0,0),(-1,-1),4),('BOTTOMPADDING',(0,0),(-1,-1),4),
        ('LEFTPADDING',(1,1),(1,-1),6),('ALIGN',(1,1),(1,-1),'LEFT'),
        ('VALIGN',(0,0),(-1,-1),'MIDDLE'),
    ]))
    story.append(itbl); story.append(Spacer(1,4*mm))

    # ── GST SUMMARY TABLE ──
    lc=float(q.get('loading_charges',0) or 0)
    ic=float(q.get('initial_charges',0) or 0)
    # Recalculate from items if stored values missing
    taxable_stored=float(q.get('taxable_subtotal',0) or 0)
    if taxable_stored==0 and taxable_sub>0: taxable_stored=taxable_sub
    # Tax base now includes loading charges + machine print/initial charges
    taxable_full=taxable_stored+lc+ic
    cgst=round(taxable_full*CGST_RATE,2) if taxable_full>0 else 0.0
    sgst=round(taxable_full*SGST_RATE,2) if taxable_full>0 else 0.0
    grand=taxable_full+cgst+sgst

    # Build summary rows
    sum_rows=[]
    sum_rows.append([Paragraph('SUMMARY',wh),Paragraph('',wh),Paragraph('',wh)])

    def srow(label,amount,style=trs,bg=None):
        return [Paragraph('',tcs),Paragraph(label,gst_lbl),Paragraph(amount,style)]

    sum_rows.append(srow('Product Subtotal (Taxable)',fmt_rs(taxable_stored)))
    if ic>0:
        mp_item_data = next((it for it in initial_items if it.get('product_type')=='Machine Printing'), None)
        mp_note_text = mp_item_data.get('mp_note','') if mp_item_data else ''
        mp_label = 'Machine Printing / Initial'
        if mp_note_text:
            mp_label += f'<br/><font size="8" color="#92400e">{mp_note_text}</font>'
        sum_rows.append(srow(mp_label, fmt_rs(ic)))
    sum_rows.append(srow('Loading Charges',fmt_rs(lc)))
    sum_rows.append(srow(f'CGST @ 9%  (on {fmt_rs(taxable_full)})',fmt_rs(cgst),gst_val))
    sum_rows.append(srow(f'SGST @ 9%  (on {fmt_rs(taxable_full)})',fmt_rs(sgst),gst_val))
    sum_rows.append([Paragraph('',tcs),Paragraph('GRAND TOTAL',gts),Paragraph(fmt_rs(grand),gts)])

    ns=len(sum_rows)
    stbl=Table(sum_rows,colWidths=[W*0.45,W*0.35,W*0.20])
    stbl.setStyle(TableStyle([
        # Header
        ('BACKGROUND',(0,0),(-1,0),BLUE),('LINEBELOW',(0,0),(-1,0),2,GOLD),
        ('SPAN',(0,0),(-1,0)),
        # Data rows
        ('ROWBACKGROUNDS',(0,1),(-1,-2),[LGRAY,ALT]),
        # Grand total row
        ('BACKGROUND',(0,-1),(-1,-1),NAVY),('LINEABOVE',(0,-1),(-1,-1),2,GOLD),
        # GST rows highlight
        ('BACKGROUND',(0,ns-3),(- 1,ns-2),GREENLT),
        # Borders
        ('BOX',(0,0),(-1,-1),1,BLUE),('LINEBELOW',(0,1),(-1,-2),0.3,MGRAY),
        ('TOPPADDING',(0,0),(-1,-1),5),('BOTTOMPADDING',(0,0),(-1,-1),5),
        ('LEFTPADDING',(0,0),(-1,-1),8),('RIGHTPADDING',(0,0),(-1,-1),8),
        ('VALIGN',(0,0),(-1,-1),'MIDDLE'),
        ('SPAN',(0,1),(0,-2)),  # empty left col spans all data rows
    ]))
    story.append(stbl); story.append(Spacer(1,6*mm))

    # ── SIGNATURE / SEAL ──
    if seal and os.path.exists(seal):
        try: seal_cell=RLImage(seal,width=30*mm,height=30*mm)
        except: seal_cell=Paragraph('',lbl)
    else: seal_cell=Paragraph('',lbl)

    sig_lbl=ps('slbl',fontName='Helvetica-Bold',fontSize=8,textColor=GRAY)
    sig_nm =ps('snm', fontName='Helvetica-Bold',fontSize=10,textColor=NAVY)
    sig_ds =ps('sds', fontName='Helvetica',     fontSize=8, textColor=GRAY)

    sig=Table([
        [Paragraph('AUTHORIZED SIGNATORY',wh),Paragraph('',wh)],
        [seal_cell,
         [Paragraph('Authorized By:',sig_lbl),Spacer(1,2*mm),
          Paragraph(contact_person,sig_nm),Paragraph(desig,sig_ds),
          Spacer(1,2*mm),Paragraph(f'For {COMPANY_NAME}',sig_ds)]]
    ],colWidths=[W*0.4,W*0.6])
    sig.setStyle(TableStyle([
        ('BACKGROUND',(0,0),(-1,0),BLUE),('LINEBELOW',(0,0),(-1,0),2,GOLD),
        ('SPAN',(0,0),(-1,0)),
        ('BACKGROUND',(0,1),(-1,1),WHITE),
        ('TOPPADDING',(0,0),(-1,-1),7),('BOTTOMPADDING',(0,0),(-1,-1),7),
        ('LEFTPADDING',(0,0),(-1,-1),8),('RIGHTPADDING',(0,0),(-1,-1),8),
        ('VALIGN',(0,1),(-1,1),'MIDDLE'),
        ('BOX',(0,0),(-1,-1),1,BLUE),
    ]))
    story.append(KeepTogether(sig)); story.append(Spacer(1,6*mm))

    # ── BANK DETAILS ──
    bk_lbl=ps('bkl',fontName='Helvetica-Bold',fontSize=8.5,textColor=NAVY)
    bk_val=ps('bkv',fontName='Helvetica',     fontSize=8.5,textColor=BLACK)
    bd=BANK_DETAILS

    # Use client's actual UCO Bank QR image
    UCO_QR_PATH = os.path.join(os.path.dirname(__file__), 'static', 'icons', 'uco_qr.png')
    qr_rl = RLImage(UCO_QR_PATH, width=38*mm, height=38*mm)

    qr_label = ps('qrl', fontName='Helvetica-Bold', fontSize=7, textColor=NAVY, alignment=TA_CENTER)
    qr_cell = Table([
        [qr_rl],
        [Paragraph('Scan to Pay (UPI)', qr_label)],
    ], colWidths=[42*mm])
    qr_cell.setStyle(TableStyle([
        ('ALIGN',(0,0),(-1,-1),'CENTER'),
        ('VALIGN',(0,0),(-1,-1),'MIDDLE'),
        ('TOPPADDING',(0,0),(-1,-1),4),
        ('BOTTOMPADDING',(0,0),(-1,-1),2),
    ]))

    bank_info = Table([
        [Paragraph('BANK DETAILS',wh)],
        [Paragraph('Account Name:',bk_lbl), Paragraph(bd['account_name'],bk_val)],
        [Paragraph('Bank Name:',bk_lbl),    Paragraph(bd['bank_name'],bk_val)],
        [Paragraph('Account No:',bk_lbl),   Paragraph(bd['account_no'],bk_val)],
        [Paragraph('IFSC Code:',bk_lbl),    Paragraph(bd['ifsc_code'],bk_val)],
        [Paragraph('Branch:',bk_lbl),       Paragraph(bd['branch'],bk_val)],
        [Paragraph('Account Type:',bk_lbl), Paragraph(bd['account_type'],bk_val)],
    ], colWidths=[(W-44*mm)*0.38, (W-44*mm)*0.62])
    bank_info.setStyle(TableStyle([
        ('BACKGROUND',(0,0),(-1,0),BLUE),('LINEBELOW',(0,0),(-1,0),2,GOLD),
        ('SPAN',(0,0),(-1,0)),
        ('ROWBACKGROUNDS',(0,1),(-1,-1),[BANKBG,BANKALT]),
        ('TOPPADDING',(0,0),(-1,-1),5),('BOTTOMPADDING',(0,0),(-1,-1),5),
        ('LEFTPADDING',(0,0),(-1,-1),8),('RIGHTPADDING',(0,0),(-1,-1),8),
        ('BOX',(0,0),(-1,-1),1,BLUE),('LINEBELOW',(0,1),(-1,-2),0.3,MGRAY),
    ]))

    bank = Table([[bank_info, qr_cell]], colWidths=[W-44*mm, 44*mm])
    bank.setStyle(TableStyle([
        ('VALIGN',(0,0),(-1,-1),'TOP'),
        ('LEFTPADDING',(0,0),(-1,-1),0),('RIGHTPADDING',(0,0),(-1,-1),0),
        ('TOPPADDING',(0,0),(-1,-1),0),('BOTTOMPADDING',(0,0),(-1,-1),0),
    ]))

    # ── TERMS & CONDITIONS — always on new page, kept together ──
    tc_num=ps('tcn',fontName='Helvetica-Bold',fontSize=8, textColor=BLUE,   alignment=TA_CENTER)
    tc_itm=ps('tci',fontName='Helvetica',     fontSize=8, textColor=BLACK,  leading=13)
    tc_rows=[[Paragraph('TERMS &amp; CONDITIONS',wh),Paragraph('',wh)]]
    for i,t in enumerate(TERMS_AND_CONDITIONS,1):
        tc_rows.append([Paragraph(str(i),tc_num),Paragraph(t,tc_itm)])
    tc=Table(tc_rows,colWidths=[W*0.06,W*0.94])
    tc.setStyle(TableStyle([
        ('BACKGROUND',(0,0),(-1,0),BLUE),('LINEBELOW',(0,0),(-1,0),2,GOLD),
        ('SPAN',(0,0),(-1,0)),
        ('ROWBACKGROUNDS',(0,1),(-1,-1),[LGRAY,ALT]),
        ('TOPPADDING',(0,0),(-1,-1),4),('BOTTOMPADDING',(0,0),(-1,-1),4),
        ('LEFTPADDING',(0,0),(-1,-1),6),('RIGHTPADDING',(0,0),(-1,-1),6),
        ('VALIGN',(0,0),(-1,-1),'MIDDLE'),
        ('BOX',(0,0),(-1,-1),1,BLUE),('LINEBELOW',(0,1),(-1,-2),0.3,MGRAY),
    ]))

    ty=ps('ty',fontName='Helvetica-BoldOblique',fontSize=11,textColor=BLUE,alignment=TA_CENTER)

    # Bank + T&C always start on a new page together
    story.append(PageBreak())
    story.append(KeepTogether(bank))
    story.append(Spacer(1,6*mm))
    story.append(KeepTogether(tc))
    story.append(Spacer(1,5*mm))
    story.append(Paragraph('Thank you for your business!',ty))

    doc.build(story); buf.seek(0); return buf

if __name__=='__main__':
    app.run(debug=True,host='0.0.0.0',port=5000)
