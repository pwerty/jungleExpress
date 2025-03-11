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
    # 로그인 정보를 알아보기위해 토큰을 얻어오기를 시도합니다.
    receivedToken = request.cookies.get('mytoken')
    # 얘가 비어있으면 100% 로그아웃 상태입니다.
    # 비어있지 않으면 올바른 로그인 상태인지 확인해야합니다.

    if receivedToken is not None:
        try:
            payload = jwt.decode(receivedToken, SECRET_KEY, algorithms=['HS256'])
            user_info = db.user.find_one({"id": payload['id']})
            return render_template('index.html', idName=user_info["id"])
        except jwt.ExpiredSignatureError:
            return render_template('index.html', idName="%")
           # return redirect(url_for('login', msg="로그인 시간이 만료되었습니다. 다시 로그인해야합니다."))
        except jwt.exceptions.DecodeError:
            return render_template('index.html', idName="%")

          #  return redirect(url_for("login", msg="로그인 정보가 없습니다."))
    else:
        # 여긴 어쨌든 로그인이 안된 영역이니 %로 로그아웃 상태임을 보내기
        return render_template('index.html', idName="%")
    

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

    isExistUser = db.user.find_one({'id': id_receive})

    if isExistUser is not None:
        return jsonify({'result': 'fail', 'msg': '이미 가입 되어 있는 아이디입니다.'})
    else:
        pw_hash = hashlib.sha256(pw_receive.encode('utf-8')).hexdigest()
        db.user.insert_one({'id': id_receive, 'pw': pw_hash, "problemList": [False] * 20, "probSolvedCnt": 0})
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
            'exp': datetime.datetime.utcnow() + datetime.timedelta(seconds=100)
        }
        token = jwt.encode(payload, SECRET_KEY, algorithm='HS256')

        # token을 줍니다.
        return jsonify({'result': 'success', 'token': token})
    # 찾지 못하면
    else:
        return jsonify({'result': 'fail', 'msg': '아이디/비밀번호가 일치하지 않습니다.'})
    

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

@app.route('/my_rank', methods=['GET'])
def my_rank():
    try:
        receivedToken = request.cookies.get('mytoken')
        payload = jwt.decode(receivedToken, SECRET_KEY, algorithms=['HS256'])
        
        # 모든 사용자를 가져와서 문제 해결 수로 정렬
        all_users = list(db.user.find({}, {'_id': 0, 'pw': 0}))
        all_users.sort(key=lambda x: x['problemList'].count(True), reverse=True)
        
        # 현재 사용자의 순위 찾기
        current_user_id = payload['id']
        my_rank = next(i + 1 for i, user in enumerate(all_users) if user['id'] == current_user_id)
        solved_count = all_users[my_rank - 1]['problemList'].count(True)
        
        return jsonify({
            'result': 'success', 
            'rank': my_rank,
            'solved_count': solved_count,
            'nickname': payload['id']
        })
        
    except (jwt.ExpiredSignatureError, jwt.exceptions.DecodeError):
        return jsonify({'result': 'fail', 'msg': '로그인이 필요합니다.'})
    

@app.route('/problems')
def problem():
    receivedToken = request.cookies.get('mytoken')    
    if receivedToken is not None:
        try:
            payload = jwt.decode(receivedToken, SECRET_KEY, algorithms=['HS256'])
            userinfo = db.user.find_one({"id": payload['id']})
            return render_template('problems.html', idName=userinfo["id"])
        except jwt.ExpiredSignatureError:
            return render_template('problems.html', idName="%")
        except jwt.exceptions.DecodeError:
            return render_template('problems.html', idName="%")
    else:
            return render_template('problems.html', idName="%")
        
if __name__ == '__main__':
    app.run('0.0.0.0', port=5001, debug=True)