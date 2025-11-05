
import React from 'react';

export const MicrophoneIcon: React.FC<{ className?: string }> = ({ className }) => (
  <svg xmlns="http://www.w3.org/2000/svg" className={className} viewBox="0 0 24 24" fill="currentColor">
    <path d="M12 2a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V5a3 3 0 0 0-3-3ZM18.707 12.293a1 1 0 0 0-1.414 0A5.002 5.002 0 0 1 12 17a5.002 5.002 0 0 1-5.293-4.707a1 1 0 0 0-1.414 1.414A7.002 7.002 0 0 0 12 19a7.002 7.002 0 0 0 6.707-5.293a1 1 0 0 0 0-1.414Z" />
    <path d="M12 21a1 1 0 0 0 1-1v-2a1 1 0 1 0-2 0v2a1 1 0 0 0 1 1Z" />
  </svg>
);

export const SpeakerIcon: React.FC<{ className?: string }> = ({ className }) => (
  <svg xmlns="http://www.w3.org/2000/svg" className={className} viewBox="0 0 24 24" fill="currentColor">
    <path d="M12 2.25c-5.376 0-9.75 4.374-9.75 9.75s4.374 9.75 9.75 9.75 9.75-4.374 9.75-9.75S17.376 2.25 12 2.25Zm-3.375 6.188a.75.75 0 0 1 1.06 0l1.813 1.812a.75.75 0 0 1 0 1.061l-1.813 1.812a.75.75 0 1 1-1.06-1.06l1.282-1.282-1.282-1.282a.75.75 0 0 1 0-1.061Zm3.435 6.094a.75.75 0 0 1 0-1.061l1.283-1.282-1.283-1.282a.75.75 0 0 1 1.06-1.061l1.813 1.812a.75.75 0 0 1 0 1.061l-1.813 1.812a.75.75 0 0 1-1.06 0Zm2.625-3.032a.75.75 0 0 1-1.06 0l-.72-.72a.75.75 0 0 1 1.06-1.061l.72.72a.75.75 0 0 1 0 1.061Z" />
  </svg>
);

export const LoadingSpinner: React.FC<{ className?: string }> = ({ className }) => (
    <svg className={`animate-spin ${className}`} xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
    </svg>
);
