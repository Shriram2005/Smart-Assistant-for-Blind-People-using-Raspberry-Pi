<?php
// Enable error reporting for debugging
error_reporting(E_ALL);
ini_set('display_errors', 1);

// Set headers
header('Access-Control-Allow-Origin: *');
header('Content-Type: application/json; charset=utf-8');

// FreeSQLDatabase Configuration
$config = [
    'host' => 'sql12.freesqldatabase.com',  // FreeSQLDatabase host
    'user' => 'sql12762218',                // FreeSQLDatabase username
    'password' => 'Ua1NUpP9R4',            // FreeSQLDatabase password
    'database' => 'sql12762218',           // FreeSQLDatabase database name
    'port' => 3306                         // FreeSQLDatabase port number
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

    // Check if table exists
    $table_check = $mysqli->query("SHOW TABLES LIKE 'captured_images'");
    if ($table_check->num_rows == 0) {
        // Create table if it doesn't exist
        $create_table = "CREATE TABLE IF NOT EXISTS captured_images (
            id INT AUTO_INCREMENT PRIMARY KEY,
            image LONGBLOB,
            original_text TEXT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
            english_translation TEXT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
            hindi_translation TEXT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
            marathi_translation TEXT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;";
        
        $mysqli->query($create_table);
    }

    // Set UTF-8 character encoding
    $mysqli->set_charset("utf8mb4");

    // Fetch the latest records
    $query = "SELECT id, original_text, english_translation, hindi_translation, marathi_translation, 
              timestamp, image FROM captured_images ORDER BY timestamp DESC";
    
    $result = $mysqli->query($query);

    if (!$result) {
        throw new Exception("Query failed: " . $mysqli->error);
    }

    $data = [];
    while ($row = $result->fetch_assoc()) {
        // Handle null values
        foreach ($row as $key => $value) {
            if ($value === null) {
                $row[$key] = "";
            }
        }

        // Convert BLOB image to base64
        if ($row['image'] && strlen($row['image']) > 0) {
            $imageData = base64_encode($row['image']);
            $row['image'] = 'data:image/jpeg;base64,' . $imageData;
        } else {
            $row['image'] = '';
        }
        
        // Clean and encode text fields
        $textFields = ['original_text', 'english_translation', 'hindi_translation', 'marathi_translation'];
        foreach ($textFields as $field) {
            if ($row[$field] && strlen($row[$field]) > 0) {
                $row[$field] = mb_convert_encoding($row[$field], 'UTF-8', 'UTF-8');
                $row[$field] = htmlspecialchars($row[$field], ENT_QUOTES, 'UTF-8');
            } else {
                $row[$field] = '';
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
        ]);
    } else {
        $json = json_encode([
            'status' => 'success',
            'data' => $data
        ], JSON_UNESCAPED_UNICODE | JSON_PARTIAL_OUTPUT_ON_ERROR);

        if ($json === false) {
            throw new Exception("JSON encoding failed: " . json_last_error_msg());
        }

        echo $json;
    }

} catch (Exception $e) {
    http_response_code(500);
    $error = [
        'status' => 'error',
        'message' => $e->getMessage(),
        'details' => [
            'error' => error_get_last(),
            'file' => __FILE__,
            'line' => __LINE__
        ]
    ];
    echo json_encode($error);
} finally {
    if (isset($result)) {
        $result->close();
    }
    if (isset($mysqli)) {
        $mysqli->close();
    }
}
?> 