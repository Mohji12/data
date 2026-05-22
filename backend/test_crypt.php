<?php
function my_simple_crypt( $string, $action = 'encrypt' ) {
    $secret_key = '9meVE6j?G!u%Z?55vSb26zGGphWJQbG*';
    $secret_iv = '9meVE6j?G!u%Z?55';
    $encrypt_method = "AES-256-CBC";
    $key = hash( 'sha256', $secret_key );
    $iv = substr( hash( 'sha256', $secret_iv ), 0, 16 );
    if( $action == 'encrypt' ) {
        return base64_encode( openssl_encrypt( $string, $encrypt_method, $key, 0, $iv ) );
    } else {
        return openssl_decrypt( base64_decode( $string ), $encrypt_method, $key, 0, $iv );
    }
}

$test_pass = "6YHNNHY6";
$encrypted = my_simple_crypt($test_pass);
echo "Password: " . $test_pass . "\n";
echo "Encrypted: " . $encrypted . "\n";

$db_pass = "SUNMallZSHF1Ybm5WUT09";
$decrypted = my_simple_crypt($db_pass, 'decrypt');
echo "DB Password: " . $db_pass . "\n";
echo "Decrypted: " . $decrypted . "\n";
?>
