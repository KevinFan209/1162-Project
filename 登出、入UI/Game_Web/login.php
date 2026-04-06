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

if ($action === 'googleLogin') {

    $id_token = $_POST['token'] ?? '';

    if (!$id_token) {
        echo json_encode(["status"=>"error","message"=>"缺少 token"]);
        exit;
    }

    // 驗證 Google Token
    $url = "https://oauth2.googleapis.com/tokeninfo?id_token=" . $id_token;
    $response = file_get_contents($url);
    $googleUser = json_decode($response, true);

    if (!isset($googleUser['email'])) {
        echo json_encode(["status"=>"error","message"=>"Google 驗證失敗"]);
        exit;
    }

    $email = $googleUser['email'];
    $username = $googleUser['name'] ?? "GoogleUser";

    // 檢查使用者是否存在
    $stmt = $db->prepare("SELECT * FROM users WHERE email=?");
    $stmt->bind_param("s", $email);
    $stmt->execute();
    $user = $stmt->get_result()->fetch_assoc();

    // 如果不存在 → 自動註冊
    if (!$user) {

        $randomPassword = password_hash(uniqid(), PASSWORD_BCRYPT);

        $stmt = $db->prepare("INSERT INTO users (username,email,password) VALUES (?,?,?)");
        $stmt->bind_param("sss", $username, $email, $randomPassword);
        $stmt->execute();

        $user_id = $stmt->insert_id;

        $user = [
            "id" => $user_id,
            "username" => $username,
            "email" => $email
        ];
    }

    // 產生 JWT（跟你原本一樣）
    $payload = [
        "iat" => time(),
        "exp" => time() + 3600,
        "data" => [
            "id" => $user['id'],
            "username" => $user['username'],
            "email" => $user['email']
        ]
    ];

    $token = JWT::encode($payload, $secretKey, 'HS256');

    echo json_encode([
        "status"=>"success",
        "token"=>$token
    ]);

    exit;
}

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

if ($action === 'refresh') {

    $token = $_POST['token'] ?? '';

    if (!$token) {
        echo json_encode(["status"=>"error"]);
        exit;
    }

    try {
        $decoded = JWT::decode($token, new Key($secretKey, 'HS256'));

        // 重新產生新 token
        $payload = [
            "iat" => time(),
            "exp" => time() + 3600,
            "data" => (array)$decoded->data
        ];

        $newToken = JWT::encode($payload, $secretKey, 'HS256');

        echo json_encode([
            "status"=>"success",
            "token"=>$newToken
        ]);

    } catch (Exception $e) {
        echo json_encode(["status"=>"error"]);
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