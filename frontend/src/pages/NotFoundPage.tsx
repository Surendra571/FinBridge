import React from 'react';
import { Link } from 'react-router-dom';
import { AlertCircle, ArrowLeft } from 'lucide-react';

export const NotFoundPage: React.FC = () => {
  return (
    <div className="min-h-[60vh] flex flex-col items-center justify-center text-center p-6">
      <div
        className="w-12 h-12 rounded-xl flex items-center justify-center mb-4"
        style={{ backgroundColor: '#FFF4E5', color: '#845400', border: '1px solid rgba(132, 84, 0, 0.2)' }}
      >
        <AlertCircle className="w-6 h-6" />
      </div>
      <h1 className="font-headline text-[22px] font-bold text-[#101B32]">Page Not Found</h1>
      <p className="font-body text-[14px] text-[#5B5F62] mt-1 max-w-sm">
        The requested financial operations workspace or resource could not be found.
      </p>
      <Link
        to="/"
        className="mt-6 inline-flex items-center space-x-2 px-4 py-2 rounded-lg text-white font-label text-[13px] font-semibold hover:opacity-95 transition"
        style={{ backgroundColor: '#5146E5' }}
      >
        <ArrowLeft className="w-4 h-4" />
        <span>Return to Dashboard</span>
      </Link>
    </div>
  );
};

export default NotFoundPage;
