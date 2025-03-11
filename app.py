from flask import Flask, render_template, jsonify, request, session, redirect, url_for

app = Flask(__name__)

from pymongo import MongoClient
import certifi
import jwt
import datetime
import hashlib

ca = certifi.where()
client = MongoClient('mongodb://localhost:27017/')
# 실제 배포 때는 일부 수정이 필요
db = client['realjungle']

SECRET_KEY = 'JUNGLE'


@app.route('/')
def home():
    receivedToken = request.cookies.get('mytoken')    

    try:
        payload = jwt.decode(receivedToken, SECRET_KEY, algorithms=['HS256'])
        user_info = db.user.find_one({"id": payload['id']})
        return render_template('index.html', nickname=user_info["nick"])
    except jwt.ExpiredSignatureError:
        return render_template('index.html', nickname="%")
        #return redirect(url_for("index"), msg="a")
       #return redirect(url_for("login", msg="로그인 시간 만료됨"))
    except jwt.exceptions.DecodeError:
       # return redirect(url_for("index"), msg="b")
       return redirect(url_for("login", msg="로그인 정보 없음"))

@app.route('/login')
def login():
    msg = request.args.get("msg")
    return render_template('login.html', msg=msg)

@app.route('/register')
def register():
    return render_template('register.html')

# [회원가입 API]
# 저장하기 전에, pw를 sha256 방법(=단방향 암호화. 풀어볼 수 없음)으로 암호화해서 저장합니다.
@app.route('/api/register', methods=['POST'])
def api_register():
    id_receive = request.form['id_give']
    pw_receive = request.form['pw_give']
    nickname_receive = request.form['nickname_give']
  
    pw_hash = hashlib.sha256(pw_receive.encode('utf-8')).hexdigest()
    db.user.insert_one({'id': id_receive, 'pw': pw_hash, 'nick': nickname_receive, "problemList": [False] * 20})

    return jsonify({'result': 'success'})


# [로그인 API]
# id, pw를 받아서 맞춰보고, 토큰을 만들어 발급합니다.
@app.route('/api/login', methods=['POST'])
def api_login():
    id_receive = request.form['id_give']
    pw_receive = request.form['pw_give']

    # 회원가입 때와 같은 방법으로 pw를 암호화합니다.
    pw_hash = hashlib.sha256(pw_receive.encode('utf-8')).hexdigest()

    # id, 암호화된pw을 가지고 해당 유저를 찾습니다.
    result = db.user.find_one({'id': id_receive, 'pw': pw_hash})

    # 찾으면 JWT 토큰을 만들어 발급합니다.
    if result is not None:
        # JWT 토큰에는, payload와 시크릿키가 필요합니다.
        # 시크릿키가 있어야 토큰을 디코딩(=풀기) 해서 payload 값을 볼 수 있습니다.
        # 아래에선 id와 exp를 담았습니다. 즉, JWT 토큰을 풀면 유저ID 값을 알 수 있습니다.
        # exp에는 만료시간을 넣어줍니다(5초). 만료시간이 지나면, 시크릿키로 토큰을 풀 때 만료되었다고 에러가 납니다.
        payload = {
            'id': id_receive,
            'exp': datetime.datetime.utcnow() + datetime.timedelta(seconds=5)
        }
        token = jwt.encode(payload, SECRET_KEY, algorithm='HS256')

        # token을 줍니다.
        return jsonify({'result': 'success', 'token': token})
    # 찾지 못하면
    else:
        return jsonify({'result': 'fail', 'msg': '아이디/비밀번호가 일치하지 않습니다.'})


# 로그인된 유저만 call 할 수 있는 API
# 유효한 토큰을 줘야 올바른 결과를 얻어갈 수 있습니다.
@app.route('/api/nick', methods=['GET'])
def api_valid():
    receivedToken = request.cookies.get('mytoken')

    try:
        # token을 시크릿키로 디코딩합니다.
        payload = jwt.decode(receivedToken, SECRET_KEY, algorithms=['HS256'])

        # payload 안에 id가 들어있습니다. 이 id로 유저정보를 찾습니다.
        # 여기에선 그 예로 닉네임을 보내주겠습니다.
        userinfo = db.user.find_one({'id': payload['id']}, {'_id': 0})
        return jsonify({'result': 'success', 'nickname': userinfo['nick']})
    except jwt.ExpiredSignatureError:
        # 위를 실행했는데 만료시간이 지났으면 에러가 납니다.
        return jsonify({'result': 'fail', 'msg': '로그인 시간이 만료되었습니다.'})
    except jwt.exceptions.DecodeError:
        return jsonify({'result': 'fail', 'msg': '로그인 정보가 존재하지 않습니다.'})


def get_ranking_data(page, per_page=10):
    # 모든 사용자를 가져와서 메모리에서 정렬
    all_users = list(db.user.find({}, {'_id': 0, 'pw': 0}))
    
    # problemList에서 True의 개수를 기준으로 정렬
    all_users.sort(key=lambda x: x['problemList'].count(True), reverse=True)
    
    total_users = len(all_users)
    total_pages = (total_users + per_page - 1) // per_page
    
    # 페이지에 해당하는 사용자들 추출
    start_idx = (page - 1) * per_page
    end_idx = start_idx + per_page
    users = all_users[start_idx:end_idx]
    
    # 각 사용자의 실제 순위 추가 (1부터 시작)
    for i, user in enumerate(users):
        user['rank'] = start_idx + i + 1
        user['solved_count'] = user['problemList'].count(True)
    
    return {
        'users': users,
        'total_pages': total_pages,
        'current_page': page,
        'total_users': total_users
    }

@app.route('/ranking', methods=['GET'])
def ranking():
    page = int(request.args.get('page', 1))
    ranking_data = get_ranking_data(page)
    return render_template('ranking.html', **ranking_data)

if __name__ == '__main__':
    app.run('0.0.0.0', port=5001, debug=True)