import { Download, Smartphone, ShieldCheck, Gamepad2 } from 'lucide-react';
import { motion } from 'framer-motion';

function App() {
  const handleDownload = () => {
    // فایل باید در پوشه public قرار داشته باشد
    const apkUrl = './app-release.apk'; 
    const link = document.createElement('a');
    link.href = apkUrl;
    link.download = 'app-release.apk';
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  return (
    <div className="min-h-screen bg-slate-950 text-white selection:bg-indigo-500/30 flex flex-col font-sans" dir="rtl">
      {/* Simple Header */}
      <nav className="fixed top-0 left-0 right-0 z-50 bg-slate-900/80 backdrop-blur-md border-b border-slate-800 h-16 flex items-center px-6">
        <div className="flex items-center gap-2">
          <Gamepad2 className="w-6 h-6 text-indigo-500" />
          <span className="text-lg font-bold">نصب‌کننده بازی</span>
        </div>
      </nav>
      
      {/* Main Content */}
      <main className="flex-grow flex items-center justify-center px-4 pt-16">
        <div className="max-w-sm w-full">
          <motion.div 
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
            className="bg-slate-900 border border-slate-800 rounded-3xl p-8 shadow-2xl text-center"
          >
            <div className="w-16 h-16 bg-indigo-600/20 rounded-2xl flex items-center justify-center mx-auto mb-6">
              <Smartphone className="w-8 h-8 text-indigo-500" />
            </div>
            
            <h1 className="text-2xl font-bold mb-3">آماده نصب هستید؟</h1>
            <p className="text-gray-400 mb-8 text-sm leading-relaxed">
              آخرین نسخه بازی را با کلیک بر روی دکمه زیر دریافت کنید.
            </p>

            <button 
              onClick={handleDownload}
              className="w-full bg-indigo-600 hover:bg-indigo-700 text-white py-4 rounded-xl font-bold text-lg flex items-center justify-center gap-3 transition-all active:scale-[0.97] shadow-lg shadow-indigo-600/20"
            >
              <Download className="w-5 h-5" />
              <span>نصب نسخه APK</span>
            </button>

            <div className="mt-6 flex items-center justify-center gap-2 text-xs text-gray-500">
              <ShieldCheck className="w-4 h-4 text-green-500" />
              <span>فایل توسط آنتی‌ویروس بررسی شده است</span>
            </div>
          </motion.div>
        </div>
      </main>

      <footer className="py-6 text-center text-gray-600 text-[10px]">
        نسخه 1.0.0
      </footer>
    </div>
  );
}

export default App;
