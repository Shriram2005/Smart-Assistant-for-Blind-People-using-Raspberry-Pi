<?php
// Prevent any output before JSON
ob_start();

// Enable error reporting for debugging but don't display errors
error_reporting(E_ALL);
ini_set('display_errors', 0);
ini_set('log_errors', 1);
ini_set('error_log', 'php_errors.log');

// Set headers
header('Access-Control-Allow-Origin: *');
header('Content-Type: application/json; charset=utf-8');

// AWS RDS Database configuration
$db_config = array(
    'host' => 'raspberrypi.c5csoekmm1vs.us-east-1.rds.amazonaws.com',
    'user' => 'admin',
    'password' => 'raspberrypi12',
    'database' => 'captured_data',
    'port' => 3306
);

// Create connection
function connectDB() {
    global $db_config;
    try {
        $conn = new mysqli(
            $db_config['host'],
            $db_config['user'],
            $db_config['password'],
            $db_config['database'],
            $db_config['port']
        );

        if ($conn->connect_error) {
            throw new Exception("Connection failed: " . $conn->connect_error);
        }

        // Set charset to handle multilingual content
        $conn->set_charset("utf8mb4");
        return $conn;
    } catch (Exception $e) {
        error_log("Database connection error: " . $e->getMessage());
        return false;
    }
}

// Get all translations with pagination
function getTranslations($page = 1, $limit = 10) {
    $offset = ($page - 1) * $limit;
    $conn = connectDB();
    
    if (!$conn) {
        return array('error' => 'Database connection failed');
    }

    try {
        // Get total count for pagination
        $count_query = "SELECT COUNT(*) as total FROM captured_images";
        $count_result = $conn->query($count_query);
        
        if (!$count_result) {
            throw new Exception("Error executing count query: " . $conn->error);
        }
        
        $total_records = $count_result->fetch_assoc()['total'];
        $total_pages = ceil($total_records / $limit);

        // Get paginated results
        $query = "SELECT id, original_text, english_translation, 
                        hindi_translation, marathi_translation, timestamp,
                        image
                 FROM captured_images 
                 ORDER BY timestamp DESC 
                 LIMIT ? OFFSET ?";
                 
        $stmt = $conn->prepare($query);
        if (!$stmt) {
            throw new Exception("Error preparing query: " . $conn->error);
        }
        
        $stmt->bind_param("ii", $limit, $offset);
        $stmt->execute();
        $result = $stmt->get_result();
        
        $translations = array();
        while ($row = $result->fetch_assoc()) {
            // Convert image BLOB to base64 for display
            if ($row['image']) {
                $row['image'] = base64_encode($row['image']);
            } else {
                $row['image'] = '';
            }
            $translations[] = $row;
        }

        return array(
            'status' => 'success',
            'data' => $translations,
            'total_pages' => $total_pages,
            'current_page' => $page,
            'total_records' => $total_records
        );

    } catch (Exception $e) {
        error_log("Error fetching translations: " . $e->getMessage());
        return array('status' => 'error', 'message' => $e->getMessage());
    } finally {
        if (isset($stmt)) {
            $stmt->close();
        }
        $conn->close();
    }
}

// Search translations
function searchTranslations($search_term) {
    $conn = connectDB();
    
    if (!$conn) {
        return array('status' => 'error', 'message' => 'Database connection failed');
    }

    try {
        $search_term = "%$search_term%";
        $query = "SELECT id, original_text, english_translation, 
                        hindi_translation, marathi_translation, timestamp,
                        image
                 FROM captured_images 
                 WHERE original_text LIKE ? 
                    OR english_translation LIKE ?
                    OR hindi_translation LIKE ?
                    OR marathi_translation LIKE ?
                 ORDER BY timestamp DESC";
                 
        $stmt = $conn->prepare($query);
        if (!$stmt) {
            throw new Exception("Error preparing search query: " . $conn->error);
        }
        
        $stmt->bind_param("ssss", $search_term, $search_term, $search_term, $search_term);
        $stmt->execute();
        $result = $stmt->get_result();
        
        $translations = array();
        while ($row = $result->fetch_assoc()) {
            if ($row['image']) {
                $row['image'] = base64_encode($row['image']);
            } else {
                $row['image'] = '';
            }
            $translations[] = $row;
        }

        return array('status' => 'success', 'data' => $translations);

    } catch (Exception $e) {
        error_log("Error searching translations: " . $e->getMessage());
        return array('status' => 'error', 'message' => $e->getMessage());
    } finally {
        if (isset($stmt)) {
            $stmt->close();
        }
        $conn->close();
    }
}

// Clean output buffer
ob_clean();

// Handle AJAX requests
if ($_SERVER['REQUEST_METHOD'] === 'GET' && isset($_GET['action'])) {
    try {
        switch ($_GET['action']) {
            case 'get_translations':
                $page = isset($_GET['page']) ? (int)$_GET['page'] : 1;
                $response = getTranslations($page);
                break;
                
            case 'search':
                $search_term = isset($_GET['term']) ? $_GET['term'] : '';
                $response = searchTranslations($search_term);
                break;
                
            default:
                $response = array('status' => 'error', 'message' => 'Invalid action');
        }
        
        echo json_encode($response);
        
    } catch (Exception $e) {
        error_log("Error processing request: " . $e->getMessage());
        echo json_encode(array('status' => 'error', 'message' => 'Internal server error'));
    }
    exit;
}
?> 