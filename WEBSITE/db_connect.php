<?php
// Enable error reporting for debugging
error_reporting(E_ALL);
ini_set('display_errors', 1);

// Set headers
header('Access-Control-Allow-Origin: *');
header('Content-Type: application/json; charset=utf-8');

// FreeSQLDatabase Configuration
$config = [
    'host' => 'sql12.freesqldatabase.com',
    'user' => 'sql12762218',
    'password' => 'Ua1NUpP9R4',
    'database' => 'sql12762218',
    'port' => 3306
];

try {
    // Test if mysqli extension is loaded
    if (!extension_loaded('mysqli')) {
        throw new Exception("MySQLi extension is not loaded");
    }

    // Create connection with error reporting
    mysqli_report(MYSQLI_REPORT_ERROR | MYSQLI_REPORT_STRICT);
    
    // Create connection
    $mysqli = new mysqli(
        $config['host'],
        $config['user'],
        $config['password'],
        $config['database'],
        $config['port']
    );

    // Set UTF-8 character encoding
    if (!$mysqli->set_charset("utf8mb4")) {
        throw new Exception("Error setting charset utf8mb4: " . $mysqli->error);
    }

    // First, let's try to alter the table to ensure proper character encoding
    try {
        $alter_table = "ALTER TABLE captured_images 
                       MODIFY original_text TEXT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
                       MODIFY english_translation TEXT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
                       MODIFY hindi_translation TEXT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
                       MODIFY marathi_translation TEXT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci";
        $mysqli->query($alter_table);
    } catch (Exception $e) {
        // If alter table fails, continue anyway
        error_log("Alter table warning: " . $e->getMessage());
    }

    // Fetch only text data (excluding image)
    $query = "SELECT id, 
              CONVERT(CAST(original_text AS BINARY) USING utf8mb4) as original_text,
              CONVERT(CAST(english_translation AS BINARY) USING utf8mb4) as english_translation,
              CONVERT(CAST(hindi_translation AS BINARY) USING utf8mb4) as hindi_translation,
              CONVERT(CAST(marathi_translation AS BINARY) USING utf8mb4) as marathi_translation,
              timestamp 
              FROM captured_images 
              ORDER BY timestamp DESC 
              LIMIT 50";
    
    $result = $mysqli->query($query);

    if (!$result) {
        throw new Exception("Query failed: " . $mysqli->error);
    }

    $data = [];
    while ($row = $result->fetch_assoc()) {
        // Handle null values and clean text fields
        $textFields = ['original_text', 'english_translation', 'hindi_translation', 'marathi_translation'];
        foreach ($textFields as $field) {
            if ($row[$field] === null || strlen($row[$field]) === 0) {
                $row[$field] = '';
            } else {
                // Convert to UTF-8 and remove any invalid characters
                $row[$field] = iconv('UTF-8', 'UTF-8//IGNORE', $row[$field]);
                $row[$field] = preg_replace('/[\x00-\x1F\x7F]/u', '', $row[$field]);
                $row[$field] = htmlspecialchars($row[$field], ENT_QUOTES | ENT_SUBSTITUTE, 'UTF-8');
            }
        }
        
        $data[] = $row;
    }

    // Check if we have any data
    if (empty($data)) {
        echo json_encode([
            'status' => 'success',
            'data' => [],
            'message' => 'No records found in the database'
        ], JSON_UNESCAPED_UNICODE | JSON_INVALID_UTF8_IGNORE);
    } else {
        $json = json_encode([
            'status' => 'success',
            'data' => $data
        ], JSON_UNESCAPED_UNICODE | JSON_INVALID_UTF8_IGNORE | JSON_PARTIAL_OUTPUT_ON_ERROR);

        if ($json === false) {
            throw new Exception("JSON encoding failed: " . json_last_error_msg() . 
                              " (Error code: " . json_last_error() . ")");
        }

        echo $json;
    }

} catch (Exception $e) {
    error_log("Database error: " . $e->getMessage());
    http_response_code(500);
    $error = [
        'status' => 'error',
        'message' => $e->getMessage(),
        'details' => [
            'error' => error_get_last(),
            'file' => __FILE__,
            'line' => __LINE__,
            'json_error' => json_last_error_msg(),
            'charset' => $mysqli->character_set_name()
        ]
    ];
    echo json_encode($error, JSON_UNESCAPED_UNICODE | JSON_INVALID_UTF8_IGNORE);
} finally {
    if (isset($result)) {
        $result->close();
    }
    if (isset($mysqli)) {
        $mysqli->close();
    }
}
?> 