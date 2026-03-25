<?php
$conn = new mysqli("localhost", "root", "admin0101", "game_db");
if ($conn->connect_error) {
    die("DB Error");
}
?>