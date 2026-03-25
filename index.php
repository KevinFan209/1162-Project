<?php
// =====================
// db.php 內容
// =====================
$conn = new mysqli("localhost", "root", "admin0101", "jwt_demo");
if ($conn->connect_error) {
    die("Connection failed: " . $conn->connect_error);
}

// =====================
// JWT 套件
// =====================
require 'vendor/autoload.php';
use Firebase\JWT\JWT;
use Firebase\JWT\Key;

// =====================
// 後端處理
// =====================
$response = "";
if ($_SERVER['REQUEST_METHOD'] === 'POST') {

    $action = $_POST['action'] ?? '';

    if($action === 'register'){
        $username = $_POST['username'] ?? '';
        $password = $_POST['password'] ?? '';
        if(!$username || !$password){
            $response = "帳號或密碼不可為空";
        } else {
            $hash = password_hash($password, PASSWORD_BCRYPT);
            $stmt = $conn->prepare("INSERT INTO users (username,password) VALUES (?,?)");
            $stmt->bind_param("ss",$username,$hash);
            if($stmt->execute()){
                $response = "註冊成功";
            } else {
                $response = "錯誤：" . $conn->error;
            }
        }
        echo $response;
        exit;
    }

    if($action === 'login'){
        $username = $_POST['username'] ?? '';
        $password = $_POST['password'] ?? '';
        $stmt = $conn->prepare("SELECT * FROM users WHERE username=?");
        $stmt->bind_param("s",$username);
        $stmt->execute();
        $user = $stmt->get_result()->fetch_assoc();
        if($user && password_verify($password,$user['password'])){
            $secretKey = "your_secret_key"; // 自訂密鑰
            $payload = [
                "user_id"=>$user['id'],
                "username"=>$user['username'],
                "exp"=>time()+3600
            ];
            $jwt = JWT::encode($payload, $secretKey, 'HS256');
            echo json_encode(["message"=>"登入成功","token"=>$jwt]);
        } else {
            echo json_encode(["message"=>"帳號或密碼錯誤"]);
        }
        exit;
    }

    if($action === 'profile'){
        $authHeader = $_POST['token'] ?? '';
        if(!$authHeader){
            echo json_encode(["message"=>"沒有 token"]); exit;
        }
        $jwt = str_replace("Bearer ","",$authHeader);
        $secretKey = "your_secret_key";
        try{
            $decoded = JWT::decode($jwt,new Key($secretKey,'HS256'));
            echo json_encode([
                "message"=>"驗證成功",
                "user_id"=>$decoded->user_id,
                "username"=>$decoded->username
            ]);
        }catch(Exception $e){
            echo json_encode(["message"=>"Token 無效"]);
        }
        exit;
    }
}
?>

<!DOCTYPE html>
<html lang="zh-TW">
<head>
<meta charset="UTF-8">
<title>JWT 單檔整合測試</title>
<style>
body { font-family: Arial, sans-serif; margin: 30px; }
input, button { margin: 5px 0; padding: 5px; }
pre { background: #f4f4f4; padding: 10px; }
</style>
</head>
<body>

<h1>JWT 單檔整合測試</h1>

<h2>註冊</h2>
<input type="text" id="regUsername" placeholder="Username"><br>
<input type="password" id="regPassword" placeholder="Password"><br>
<button onclick="register()">註冊</button>
<pre id="regResult"></pre>

<h2>登入</h2>
<input type="text" id="loginUsername" placeholder="Username"><br>
<input type="password" id="loginPassword" placeholder="Password"><br>
<button onclick="login()">登入</button>
<pre id="loginResult"></pre>

<h2>取得個人資料 (JWT)</h2>
<button onclick="getProfile()">取得資料</button>
<pre id="profileResult"></pre>

<h2>登出</h2>
<button onclick="logout()">登出</button>
<pre id="logoutResult"></pre>

<script>
let token = "";

// 註冊
function register(){
    const username = document.getElementById('regUsername').value;
    const password = document.getElementById('regPassword').value;

    fetch('index.php',{
        method:'POST',
        headers:{'Content-Type':'application/x-www-form-urlencoded'},
        body:`action=register&username=${encodeURIComponent(username)}&password=${encodeURIComponent(password)}`
    })
    .then(res=>res.text())
    .then(data=>document.getElementById('regResult').textContent=data)
    .catch(err=>console.error(err));
}

// 登入
function login(){
    const username = document.getElementById('loginUsername').value;
    const password = document.getElementById('loginPassword').value;

    fetch('index.php',{
        method:'POST',
        headers:{'Content-Type':'application/x-www-form-urlencoded'},
        body:`action=login&username=${encodeURIComponent(username)}&password=${encodeURIComponent(password)}`
    })
    .then(res=>res.json())
    .then(data=>{
        document.getElementById('loginResult').textContent=JSON.stringify(data,null,2);
        if(data.token){
            token=data.token;
            localStorage.setItem("jwtToken",token);
        }
    })
    .catch(err=>console.error(err));
}

// 取得個人資料
function getProfile(){
    if(!token) token = localStorage.getItem("jwtToken");
    if(!token){ alert("請先登入"); return; }

    fetch('index.php',{
        method:'POST',
        headers:{'Content-Type':'application/x-www-form-urlencoded'},
        body:`action=profile&token=${encodeURIComponent("Bearer "+token)}`
    })
    .then(res=>res.json())
    .then(data=>document.getElementById('profileResult').textContent=JSON.stringify(data,null,2))
    .catch(err=>console.error(err));
}

// 登出
function logout(){
    token="";
    localStorage.removeItem("jwtToken");
    document.getElementById('logoutResult').textContent="已登出";
    document.getElementById('profileResult').textContent="";
    document.getElementById('loginResult').textContent="";
}
</script>

</body>
</html>