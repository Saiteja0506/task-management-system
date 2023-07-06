from flask import Flask,render_template,request,redirect,url_for,session,abort,send_file,flash
import mysql.connector
from datetime import datetime
import os
from itsdangerous import URLSafeTimedSerializer
from s_token import token
from key import salt1,salt2,secret_key
from flask_session import Session
from smail import sendmail
#mydb=mysql.connector.connect(host='localhost',user='root',password='admin',db='tms')
app=Flask(__name__)
app.config['SESSION_TYPE']='filesystem'
app.secret_key=secret_key
Session(app)
db=os.environ['RDS_DB_NAME']
user=os.environ['RDS_USERNAME']
password=os.environ['RDS_PASSWORD']
host=os.environ['RDS_HOSTNAME']
port=os.environ['RDS_PORT']
with mysql.connector.connect(host= host,user=user,password=password,db=db) as conn:
    cursor=conn.cursor(buffered=True)
    cursor.execute('create table if not exists admin(username varchar(30),password varchar(30),email varchar(50) primary key,email_status enum("confirmed","not confirmed")default not confirmed)')
    cursor.execute('create table if not exists user(username varchar(30)unique,department varchar(30),usermail varchar(50) primary key,userpassword varchar(20),added_by varchar(50),foreign key(usermail) references admin(email))')
    cursor.execute('create table if not exists task(taskid int primary key,title varchar(50)),due_date varchar(10),description text,usermail varchar(50),added_by varchar(50),status enum("not started","in progress","on hold","completed","not updated")default "not updated",foreign key(usermail) references user(usermail),foreign key(added_by) references admin(mail)')
mydb=mysql.connector.connect(host= host,user=user,password=password,db=db)
@app.route('/')
def index():
    return render_template('index.html')
@app.route('/admreg',methods=['GET','POST'])
def admreg():
    if request.method=='POST':
        username=request.form['username']
        password=request.form['password']
        email=request.form['email']
        cursor=mydb.cursor(buffered=True)
        try:
            cursor.execute('insert into admin(username,password,email) values(%s,%s,%s)',[username,password,email])
        except mysql.connector.IntegrityError:
            flash('username or email already in use')
        else:
            mydb.commit()
            cursor.close()
            subject='CONFIRMATION LINK'
            confirm_link=url_for('confirm',token=token(email,salt1),_external=True)
            body=f"THANKS FOR REGISTRATION\nCLICK THE BELOW LINK FOR CONFIRMATION\n\n\n{confirm_link}"
            sendmail(to=email,subject=subject,body=body)
            flash('confirmation link sent to your email')
            return redirect(url_for('admreg'))
    return render_template('admreg.html')
@app.route('/confirm/<token>')
def confirm(token):
    try:
        serializer=URLSafeTimedSerializer(secret_key)
        email=serializer.loads(token,salt=salt1,max_age=120)
    except Exception as e:
        abort(404,'link expired')
    else:
        cursor=mydb.cursor(buffered=True)
        cursor.execute('select email_status from admin where email=%s',[email])
        status=cursor.fetchone()[0]
        cursor.close()
        if status=='confirmed':
            flash('mail already registered')
            return redirect(url_for('admlog'))
        else:
            cursor=mydb.cursor(buffered=True)
            cursor.execute('update admin set email_status="confirmed" where email=%s',[email])
            mydb.commit()
            cursor.close()
            flash('email registered successfully')
            return redirect(url_for('admlog'))
@app.route('/admlog',methods=['POST','GET'])
def admlog():
    if session.get('admin'):
        return redirect(url_for('admhome'))
    if request.method=='POST':
        username=request.form['username']
        password=request.form['password']
        cursor=mydb.cursor(buffered=True)
        cursor.execute('select count(*) from admin where username=%s',[username])
        count=cursor.fetchone()[0]
        if count==1:
            cursor.execute('select count(*) from admin where username=%s and password=%s',[username,password])
            pcount=cursor.fetchone()[0]
            if pcount==1:
                session['admin']=username
                cursor.execute('select email_status from admin where username=%s',[username])
                status=cursor.fetchone()[0]
                cursor.close()
                if status!='confirmed':
                    return redirect(url_for('inactive'))
                else:
                    return redirect(url_for('admhome'))
            else:
                cursor.close()
                flash('incorrect password')
                return render_template('admlog.html')
        else:
            cursor.close()
            flash('invalid username')
            return render_template('admlog.html')
    return render_template('admlog.html')
@app.route('/inactive')
def inactive():
    if session.get('admin'):
        username=session.get('admin')
        cursor=mydb.cursor(buffered=True)
        cursor.execute('select email_status from admin where username=%s',[username])
        status=cursor.fetchone()[0]
        cursor.close()
        if status=='confirmed':
            return redirect(url_for('adhome'))
        else:
            return render_template('inactive.html')
    else:
        return redirect(url_for('admlog'))
@app.route('/resend')
def resend():
    if session.get('admin'):
        username=session.get('admin')
        cursor=mydb.cursor(buffered=True)
        cursor.execute('select email_status from admin where username=%s',[username])
        status=cursor.fetchone()[0]
        cursor.execute('select email from admin where username=%s',[username])
        email=cursor.fetchone()[0]
        if status=='confirmed':
            flash('your email was already confirmed')
            return redirect(url_for('admhome'))
        else:
            subject='EMAIL CONFIRMATION'
            confirmlink=url_for('confirm',token=token(email,salt1),_external=True)
            body=f"CLICK THE BELOW LINK TO ACTIVE YOUR EMAIL ACCOUNT\n\n\n{confirmlink}"
            sendmail(to=email,subject=subject,body=body)
            flash('confirmation link sent to your email')
            return redirect(url_for('inactive'))
    else:
        return render_template('admlog.html')
@app.route('/logout')
def logout():
    if session.get('admin'):
        session.pop('admin')
        return redirect(url_for('index'))
    else:
        return render_template('admlog.html')
@app.route('/forgot',methods=['POST','GET'])
def forgot():
    if request.method=='POST':
        email=request.form['email']
        cursor=mydb.cursor(buffered=True)
        cursor.execute('select count(*) from admin where email=%s',[email])
        count=cursor.fetchone()[0]
        cursor.close()
        if count==1:
            cursor=mydb.cursor(buffered=True)
            cursor.execute('select email_status from admin where email=%s',[email])
            status=cursor.fetchone()[0]
            if status!='confirmed':
                flash('please confirm your email first')
                return redirect(url_for('resetinactive'))
            else:
                subject='PASSWORD RESET LINK'
                confirm_link=url_for('reset',token=token(email,salt2),_external=True)
                body=f"CLICK THE BELOW TO RESET PASSWORD\n\n\n{confirm_link}"
                sendmail(to=email,subject=subject,body=body)
                flash('email sent successfully for reset password check your email')
                return redirect(url_for('admlog'))
        else:
            flash('invalid email please enter registered email')
            return render_template('forgot.html')
    return render_template('forgot.html')
        
@app.route('/reset/<token>',methods=['POST','GET'])
def reset(token):
    try:
        serializer=URLSafeTimedSerializer(secret_key)
        email=serializer.loads(token,salt=salt2,max_age=120)
    except Exception as e:
        abort(404,'link expired')
    else:
        if request.method=='POST':
            newpassword=request.form['npassword']
            confirmpassword=request.form['cpassword']
            if newpassword==confirmpassword:
                cursor=mydb.cursor(buffered=True)
                cursor.execute('update admin set password=%s where email=%s',[newpassword,email])
                mydb.commit()
                cursor.close()
                flash('newpassword updated successfully')
                return redirect(url_for('admlog'))
            else:
                flash('passwords mismatched enter again')
                return render_template('newpassword.html')
        return render_template('newpassword.html')
@app.route('/resetinactive',methods=['GET','POST'])
def resetinactive():
    if request.method=='POST':
        email=request.form['email']
        cursor=mydb.cursor(buffered=True)
        cursor.execute('select count(*) from admin where email=%s',[email])
        present=cursor.fetchone()[0]
        cursor.close()
        if present==1:
            subject='confirmation link'
            confirm_link=url_for('confirm',token=token(email,salt1),_external=True)
            body=f"please click below link to active your email account\n\n\n{confirm_link}"
            sendmail(to=email,subject=subject,body=body)
            flash('email confirmation link sent')
            return redirect(url_for('admlog'))
        else:
            flash('please entered valid email id')
            return render_template('resetinactive.html')
    return render_template('resetinactive.html')
@app.route('/admhome')
def admhome():
    if session.get('admin'):
        return render_template('admhome.html')
    else:
        return redirect(url_for('admlog'))
@app.route('/adm_tt')
def adm_tt():
    if session.get('admin'):
        cursor=mydb.cursor(buffered=True)
        cursor.execute('select email from admin where username=%s',[session.get('admin')])
        email=cursor.fetchone()[0]
        cursor.execute('select * from task where added_by=%s',[email])
        data=cursor.fetchall()
        return render_template('adm_tt.html',data=data)
    else:
        return redirect(url_for('admlog'))
@app.route('/updatetask/<taskid>',methods=['POST','GET'])
def updatetask(taskid):
    if session.get('admin'):
        cursor=mydb.cursor(buffered=True)
        cursor.execute('select title,due_date,description from task where taskid=%s',[taskid])
        title,due_date,description=cursor.fetchone()
        cursor.close()
        if request.method=='POST':
            title=request.form['title']
            due_date=request.form['due_date']
            description=request.form['description']
            cursor=mydb.cursor(buffered=True)
            cursor.execute('update task set title=%s,due_date=%s,description=%s where taskid=%s',[title,due_date,description,taskid])
            mydb.commit()
            cursor.close()
            return redirect(url_for('adm_tt'))
        return render_template('updatetask.html',title=title,due_date=due_date,description=description)
    else:
        return redirect(url_for('admlog'))
@app.route('/deletetask/<taskid>',methods=['POST','GET'])
def deletetask(taskid):
    if session.get('admin'):
        cursor=mydb.cursor(buffered=True)
        cursor.execute('delete from task where taskid=%s',[taskid])
        mydb.commit()
        cursor.close()
        return redirect(url_for('adm_tt'))
    else:
        return redirect(url_for('admlog'))
@app.route('/adduser',methods=['POST','GET'])
def adduser():
    if session.get('admin'):
        if request.method=='POST':
            admin=session.get('admin')
            username=request.form['username']
            department=request.form['department']
            usermail=request.form['usermail']
            userpassword=request.form['password']
            cursor=mydb.cursor(buffered=True)
            cursor.execute('select email from admin where username=%s',[admin])
            email=cursor.fetchone()[0]
            try:
                cursor.execute('insert into user(username,department,usermail,userpassword,added_by) values(%s,%s,%s,%s,%s)',[username,department,usermail,userpassword,email])
            except Exception as e:
                cursor.close()
                flash('username or email already exists,try another')
                return redirect(url_for('adduser'))
            else:
                mydb.commit()
                cursor.close()
                flash('user added successfully')
                subject="LOGIN CREDINTIALS"
                body=f"HELLO FOLK!\n\n\nYOUR LOGIN CREDENTIALS\n\nusername :{username}\n\npassword :{userpassword}"
                sendmail(to=usermail,subject=subject,body=body)
                return redirect(url_for('adduser'))
        return render_template('adduser.html')
    else:
        return redirect(url_for('admlog'))
@app.route('/addtask',methods=['POST','GET'])
def addtask():
    if session.get('admin'):
        username=session.get('admin')
        cursor=mydb.cursor(buffered=True)
        cursor.execute('select email from admin where username=%s',[username])
        added_by=cursor.fetchone()[0]
        cursor.execute('select usermail from user where added_by=%s',[added_by])
        data=cursor.fetchall()
        if request.method=='POST':
            admin=session.get('user')
            taskid=request.form['taskid']
            title=request.form['title']
            due_date=request.form['due_date']
            description=request.form['description']
            usermail=request.form['usermail']
            cursor=mydb.cursor(buffered=True)
            cursor.execute('select email from admin where username=%s',[admin])
            added_by=cursor.fetchone()[0]
            try:
                cursor.execute('insert into task(taskid,title,due_date,description,usermail,added_by) values(%s,%s,%s,%s,%s,%s)',[taskid,title,due_date,description,usermail,added_by])
            except Exception as e:
                cursor.close()
                flash('taskid already exists')
                return redirect(url_for('addtask'))
            else:
                mydb.commit()
                cursor.close()
                flash('task added successfully')
                return redirect(url_for('addtask'))
        return render_template('addtask.html',data=data)
    else:
        return redirect(url_for('admlog'))
@app.route('/userlog',methods=['POST','GET'])
def userlog():
    if session.get('user'):
        return redirect(url_for('userhome'))
    if request.method=='POST':
        username=request.form['username']
        password=request.form['password']
        cursor=mydb.cursor(buffered=True)
        cursor.execute('select count(*) from user where username=%s',[username])
        count=cursor.fetchone()[0]
        if count==1:
            cursor.execute('select count(*) from user where userpassword=%s',[password])
            pcount=cursor.fetchone()[0]
            if pcount==1:
                session['user']=username
                return redirect(url_for('userhome'))
            else:
                flash('incorrect password')
                return redirect(url_for('userlog'))
        else:
            flash('invalid username')
            return redirect(url_for('userlog'))
    return render_template('userlog.html')
@app.route('/userhome',methods=['POST','GET'])
def userhome():
    if session.get('user'):
        username=session.get('user')
        cursor=mydb.cursor(buffered=True)
        cursor.execute('select usermail from user where username=%s',[username])
        usermail=cursor.fetchone()[0]
        cursor.execute('select * from task where usermail=%s',[usermail])
        data=cursor.fetchall()
        cursor.close()
        if request.method=='POST':
            cursor=mydb.cursor(buffered=True)
            taskid=request.form['taskid']
            status=request.form['status']
            cursor.execute('update task set status=%s where taskid=%s',[status,taskid])
            mydb.commit()
            cursor.close()
            return redirect(url_for('userhome'))
        return render_template('userhome.html',data=data)
    else:
        return redirect(url_for('userlog'))
@app.route('/userlogout')
def userlogout():
    if session.get('user'):
        session.pop('user')
        return redirect(url_for('index'))
    else:
        return render_template('admlog.html')
app.run(use_reloader=True,debug=True)