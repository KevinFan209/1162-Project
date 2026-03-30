<?php
header('Content-Type: application/json; charset=utf-8');

require 'vendor/autoload.php';

use Firebase\JWT\JWT;
use Firebase\JWT\Key;

/* ================= 設定 ================= */
$secretKey = "NCNU_IM_Project_Super_Secret_Key_2026"; // 至少32字元

$db = new mysqli("localhost", "root", "admin0101", "game_web");

if ($db->connect_error) {
    echo json_encode(["status"=>"error","message"=>"資料庫連線失敗"]);
    exit;
}

$action = $_POST['action'] ?? '';

/* ================= 註冊 ================= */
if ($action === 'register') {

    $username = trim($_POST['username'] ?? '');
    $email    = trim($_POST['email'] ?? '');
    $password = $_POST['password'] ?? '';

    if (!$username || !$email || !$password) {
        echo json_encode(["status"=>"error","message"=>"請填寫所有欄位"]);
        exit;
    }

    // 檢查 email 是否存在
    $check = $db->prepare("SELECT id FROM users WHERE email=?");
    $check->bind_param("s", $email);
    $check->execute();

    if ($check->get_result()->num_rows > 0) {
        echo json_encode(["status"=>"error","message"=>"Email 已被註冊"]);
        exit;
    }

    // 密碼加密
    $hash = password_hash($password, PASSWORD_BCRYPT);

    $stmt = $db->prepare("INSERT INTO users (username,email,password) VALUES (?,?,?)");
    $stmt->bind_param("sss", $username, $email, $hash);

    if ($stmt->execute()) {
        echo json_encode(["status"=>"success","message"=>"註冊成功"]);
    } else {
        echo json_encode(["status"=>"error","message"=>"註冊失敗"]);
    }

    exit;
}

/* ================= 登入 ================= */
if ($action === 'login') {

    $email    = $_POST['email'] ?? '';
    $password = $_POST['password'] ?? '';

    if (!$email || !$password) {
        echo json_encode(["status"=>"error","message"=>"請輸入帳號密碼"]);
        exit;
    }

    $stmt = $db->prepare("SELECT * FROM users WHERE email=?");
    $stmt->bind_param("s", $email);
    $stmt->execute();

    $user = $stmt->get_result()->fetch_assoc();

    if ($user && password_verify($password, $user['password'])) {

        // JWT payload
        $payload = [
            "iat" => time(),
            "exp" => time() + 3600, // 1 小時
            "data" => [
                "id" => $user['id'],
                "username" => $user['username'],
                "email" => $user['email']
            ]
        ];

        $token = JWT::encode($payload, $secretKey, 'HS256');

        echo json_encode([
            "status" => "success",
            "token"  => $token
        ]);

    } else {
        echo json_encode([
            "status"=>"error",
            "message"=>"帳號或密碼錯誤"
        ]);
    }

    exit;
}

/* ================= JWT 驗證 ================= */
if ($action === 'verify') {

    $token = str_replace("Bearer ", "", $_POST['token'] ?? '');

    if (!$token) {
        echo json_encode(["status"=>"error","message"=>"缺少 token"]);
        exit;
    }

    try {
        $decoded = JWT::decode($token, new Key($secretKey, 'HS256'));

        echo json_encode([
            "status"=>"success",
            "user"=>$decoded->data
        ]);

    } catch (Exception $e) {
        echo json_encode([
            "status"=>"error",
            "message"=>"Token 無效或過期"
        ]);
    }

    exit;
}
?>