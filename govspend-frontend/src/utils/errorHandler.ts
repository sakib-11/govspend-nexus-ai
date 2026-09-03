import { toast } from 'react-hot-toast';

export class ErrorHandler {
  static handle(error: any): string {
    let message = 'An unexpected error occurred. Please try again.';

    if (error?.response) {
      // Server responded with error
      switch (error.response.status) {
        case 400:
          message = error.response.data?.detail || 'Invalid request. Please check your input.';
          break;
        case 401:
          message = 'Your session has expired. Please login again.';
          break;
        case 403:
          message = 'You do not have permission to perform this action.';
          break;
        case 404:
          message = 'The requested resource was not found.';
          break;
        case 409:
          message = 'Conflict: The resource may have been modified.';
          break;
        case 422:
          message = 'Validation error. Please check your input.';
          break;
        case 429:
          message = 'Too many requests. Please wait and try again.';
          break;
        case 500:
          message = 'An internal server error occurred. Our team has been notified.';
          break;
        default:
          message = error.response.data?.detail || message;
      }
    } else if (error?.request) {
      // Request made but no response
      message = 'Unable to connect to the server. Working in resilient offline fallback mode.';
    }

    // Show error toast with pastel styling
    toast.error(message, {
      style: {
        background: '#E8C4C4',
        color: '#3D1A1A',
        borderRadius: '12px',
        padding: '16px 20px',
        fontWeight: 500,
      },
      icon: '⚠️',
    });

    return message;
  }
}

export default ErrorHandler;
