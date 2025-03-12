from flask import Flask, render_template, jsonify, request, session, redirect, url_for
from flask.json.provider import JSONProvider
from bson import ObjectId
import json
app = Flask(__name__)

from dotenv import load_dotenv
from pymongo import MongoClient
import os
import certifi
import jwt
import datetime
import hashlib

load_dotenv()
ca = certifi.where()
client = MongoClient('mongodb://localhost:27017/')
# 실제 배포 때는 일부 수정이 필요
db = client['realjungle']

answers=["jingle","jungle","eagle","bagel","zigle"]



#####################################################################################
# 각 메모에 _id를 사용하려고 하니 해당 내용이 없으면 사용이 어려워 쓰게 된 내용
# ObjectId 타입으로 되어있는 _id 필드는 Flask 의 jsonify 호출시 문제가 된다.
# 이를 처리하기 위해서 기본 JsonEncoder 가 아닌 custom encoder 를 사용한다.
class CustomJSONEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, ObjectId):
            return str(o)
        return json.JSONEncoder.default(self, o)


class CustomJSONProvider(JSONProvider):
    def dumps(self, obj, **kwargs):
        return json.dumps(obj, **kwargs, cls=CustomJSONEncoder)

    def loads(self, s, **kwargs):
        return json.loads(s, **kwargs)


# 위에 정의되 custom encoder 를 사용하게끔 설정한다.
app.json = CustomJSONProvider(app)

# 여기까지 이해 못해도 그냥 넘어갈 코드입니다.
# #####################################################################################



SECRET_KEY = os.getenv('SECRET_KEY')


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
    receivedToken = request.cookies.get('mytoken')

    if receivedToken is None:
        return render_template('login.html')
    else:
        try:
            payload = jwt.decode(receivedToken, SECRET_KEY, algorithms=['HS256'])
            user_info = db.user.find_one({"id": payload['id']})
            return render_template('index.html', idName=user_info["id"])
        except jwt.ExpiredSignatureError:
            return render_template('login.html')
        except jwt.exceptions.DecodeError:
            return render_template('login.html')

@app.route('/register')
def register():
    receivedToken = request.cookies.get('mytoken')

    if receivedToken is not None:
        try:
            payload = jwt.decode(receivedToken, SECRET_KEY, algorithms=['HS256'])
            user_info = db.user.find_one({"id": payload['id']})
            return render_template('index.html', idName=user_info["id"])
        except jwt.ExpiredSignatureError:
            return render_template('register.html')
        except jwt.exceptions.DecodeError:
            return render_template('register.html')
    else:
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
            'exp': datetime.datetime.utcnow() + datetime.timedelta(seconds=1000000)
        }
        token = jwt.encode(payload, SECRET_KEY, algorithm='HS256')

        # token을 줍니다.
        return jsonify({'result': 'success', 'token': token})
    # 찾지 못하면
    else:
        return jsonify({'result': 'fail', 'msg': '아이디/비밀번호가 일치하지 않습니다.'})
    

def update_ranking_collection(all_users):
        # ranking 컬렉션에 사용자 순위 정보 업데이트
        ranking_updates = []
        for user in all_users:  # 전체 사용자에 대해 순위 정보 생성
            ranking_data = {
                'user_id': user['id'],
                'rank': all_users.index(user) + 1,
                'solved_count': user['problemList'].count(True),
                'updated_at': datetime.datetime.utcnow()
            }
            ranking_updates.append(ranking_data)
        
        # 기존 ranking 컬렉션 데이터 삭제 후 새로운 데이터 삽입
        db.ranking.delete_many({})
        if ranking_updates:
            db.ranking.insert_many(ranking_updates)
    

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
    
    update_ranking_collection(all_users)
    
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


@app.route('/add_friend', methods=['POST'])
def add_friend():
    try:
        token = request.cookies.get('mytoken')
        payload = jwt.decode(token, SECRET_KEY, algorithms=['HS256'])
        user_id = payload['id']
        friend_id = request.form['friend_id']
        
        # 자기 자신은 친구 추가 불가
        if user_id == friend_id:
            return jsonify({'result': 'fail', 'msg': '자기 자신은 친구 추가할 수 없습니다.'})
            
        # 이미 친구인 경우 체크
        user = db.friends.find_one({'user_id': user_id, 'friend_id': friend_id})
        if user is not None:
            return jsonify({'result': 'fail', 'msg': '이미 친구입니다.'})
            
        # 친구 추가
        db.friends.insert_one({
            'user_id': user_id,
            'friend_id': friend_id
        })
        return jsonify({'result': 'success'})
    except:
        return jsonify({'result': 'fail', 'msg': '로그인이 필요합니다.'})
    

@app.route('/friend_ranking', methods=['GET'])
def friend_ranking():
    try:
        token = request.cookies.get('mytoken')
        payload = jwt.decode(token, SECRET_KEY, algorithms=['HS256'])
        user_id = payload['id']
        
        # 현재 사용자의 친구 목록 가져오기
        friends_list = list(db.friends.find({'user_id': user_id}))
        friends = [friend['friend_id'] for friend in friends_list]
        
        # 친구들의 정보 가져오기 (rank 필드 제외)
        friend_rank = list(db.ranking.find(
            {'user_id': {'$in': friends}}, 
            {'_id': 0, 'pw': 0, 'updated_at': 0}
        ))
        
        return jsonify({
            'result': 'success',
            'friends': friend_rank
        })
    except:
        return jsonify({'result': 'fail', 'msg': '로그인이 필요합니다.'})

@app.route('/problems')
def problem():
    receivedToken = request.cookies.get('mytoken')    
    
    try:
        payload = jwt.decode(receivedToken, SECRET_KEY, algorithms=['HS256'])
        userinfo = db.user.find_one({"id": payload['id']})
        return render_template('problems.html', idName=userinfo["id"], solvedProblems=userinfo["problemList"])
    except jwt.ExpiredSignatureError:
        return render_template('problems.html', idName="%", solvedProblems=[])
    except jwt.exceptions.DecodeError:
        return render_template('problems.html', idName="%", solvedProblems=[])   

    
@app.route('/api/problems', methods=['POST'])
def solved():
    id_receive = request.form['id_give']
    number_receive = int(request.form['number_give'])
    answer_receive=request.form['answer_give']

    correct=answer_receive==answers[number_receive]

    if(correct==True):
        if(id_receive!="%"):
            user_info = db.user.find_one({"id": id_receive})

            user_info["problemList"][number_receive] = True
            
            user_info["probSolvedCnt"] += 1
            db.user.update_one({"id": id_receive}, {"$set": {"problemList": user_info["problemList"], "probSolvedCnt": user_info["probSolvedCnt"]}})
            return jsonify({'result': 'success', 'msg':'correct'})
        if(id_receive=="%"):
            return jsonify({'result': 'success', 'msg':'correct'})
    else:
        return jsonify({'result': 'success', 'msg':'incorrect'})
    


@app.route('/api/comments', methods=['GET'])
def getComments():
    # 이 코드는 특정한 문제에 작성된 댓글 목록을 가져오는 것이 목적입니다.
    # probNum이라는 값을 프론트에서 가져올 예정입니다. 이 값은 프론트에서 문제 번호를 갖다 주면 됩니다.
    probNum_receive = request.args.get('probNum')

    # 문제 번호를 통해 댓글을 찾아봅니다. comments 라는 새로운 데이터베이스를 활용합니다.
    searchResult = list(db.comments.find({"problemNum": probNum_receive}))
    # searchResult는 테이블이고 각 레코드마다 _id, (user)id, contents, problemNum이 담깁니다.
    # 이건 html 상에서 makeCard 만들던 내용을 참고하면 좋곘네요
    # https://kraftonjungle.notion.site/Chapter-4-4ab9bb5d065048b596d21e8fd5e4b708
    return jsonify({'result': 'success', 'list': searchResult})

@app.route('/api/comments', methods=['POST'])
def postComments():
    # 이 코드는 특정한 문제에 댓글을 작성하기 위한 것 입니다.
    # probNum이라는 값을 프론트에서 가져올 예정입니다. 이 값은 프론트에서 문제 번호를 갖다 주면 됩니다.
    probNum_receive = request.form['probNum']
    id_receive = request.form['whoPosting']
    contents = request.form['contents']
    db.comments.insert_one({'userID': id_receive, 'contents': contents, 'problemNum': probNum_receive})
    return jsonify({'result': 'success'})

@app.route('/api/comments/delete', methods=['POST'])
def delComments():
    # 이 코드는 특정한 문제에 댓글을 삭 제 하기위한 것 입니다.
    db_id_receive = request.form['db_id']
    id_receive = request.form['whoRequested']
    delTarget = db.comments.delete_one({'_id': ObjectId(db_id_receive), 'userID':id_receive})
    if delTarget.deleted_count > 0:
        return jsonify({'result': 'success'})
    else:
        return jsonify({'result': 'failed'})

    


if __name__ == '__main__':
    app.run('0.0.0.0', port=5001, debug=True)