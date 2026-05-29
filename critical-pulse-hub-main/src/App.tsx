import { lazy, Suspense, useEffect } from 'react';
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { Toaster } from '@/components/ui/sonner';

// Core pages (loaded immediately)
import Home from '@/pages/Home';
import Login from '@/pages/Login';
import Register from '@/pages/Register';
import QuizExam from '@/pages/dashboard/QuizExam';
import { EVENT_SLUG, EVENT_SLUG_LEGACY } from '@/lib/eventConclave';

// Lazy loaded pages
const Faculty = lazy(() => import('@/pages/Faculty'));
const Gallery = lazy(() => import('@/pages/Gallery'));
const FAQ = lazy(() => import('@/pages/FAQ'));
const Contact = lazy(() => import('@/pages/Contact'));
const Awards = lazy(() => import('@/pages/Awards'));
const Publications = lazy(() => import('@/pages/Publications'));
const Membership = lazy(() => import('@/pages/Membership'));
const ProfessionalMembership = lazy(() => import('@/pages/ProfessionalMembership'));
const NotFound = lazy(() => import('@/pages/NotFound'));
const ForgotPassword = lazy(() => import('@/pages/ForgotPassword'));
const ResetPassword = lazy(() => import('@/pages/ResetPassword'));
const ThankYou = lazy(() => import('@/pages/ThankYou'));
const RegistrationFeePage = lazy(() => import('@/pages/RegistrationFeePage'));
const EventConclaveRegister = lazy(() => import('@/pages/EventConclaveRegister'));
const EventConclaveThankYou = lazy(() => import('@/pages/EventConclaveThankYou'));

// Layouts & Protected Routes
import StudentLayout from '@/components/StudentLayout';
import AdminLayout from '@/components/AdminLayout';
import { ProtectedRoute, AdminRoute } from '@/components/ProtectedRoute';

// Student Dashboard (Lazy)
const Dashboard = lazy(() => import('@/pages/dashboard/Dashboard'));
const Videos = lazy(() => import('@/pages/dashboard/Videos'));
const VideoDetail = lazy(() => import('@/pages/dashboard/VideoDetail'));
const Quiz = lazy(() => import('@/pages/dashboard/Quiz'));
const QuizResult = lazy(() => import('@/pages/dashboard/QuizResult'));
const Profile = lazy(() => import('@/pages/dashboard/Profile'));
const Payments = lazy(() => import('@/pages/dashboard/Payments'));
const ExtendSubscription = lazy(() => import('@/pages/dashboard/ExtendSubscription'));
const Certificate = lazy(() => import('@/pages/dashboard/Certificate'));

// Admin Pages (Lazy)
const AdminDashboard = lazy(() => import('@/pages/admin/AdminDashboard'));
const AdminUsers = lazy(() => import('@/pages/admin/AdminUsers'));
const AdminUserDetail = lazy(() => import('@/pages/admin/AdminUserDetail'));
const AdminVideos = lazy(() => import('@/pages/admin/AdminVideos'));
const AdminFolders = lazy(() => import('@/pages/admin/AdminFolders'));
const AdminBatches = lazy(() => import('@/pages/admin/AdminBatches'));
const AdminExams = lazy(() => import('@/pages/admin/AdminExams'));
const AdminQuestions = lazy(() => import('@/pages/admin/AdminQuestions'));
const AdminResults = lazy(() => import('@/pages/admin/AdminResults'));
const AdminCoupons = lazy(() => import('@/pages/admin/AdminCoupons'));
const AdminSettings = lazy(() => import('@/pages/admin/AdminSettings'));
const AdminLoginActivity = lazy(() => import('@/pages/admin/AdminLoginActivity'));
const AdminLoginPage = lazy(() => import('@/pages/admin/AdminLoginPage'));
const AdminPayments = lazy(() => import('@/pages/admin/AdminPayments'));
const AdminPackages = lazy(() => import('@/pages/admin/AdminPackages'));
const AdminQuizSections = lazy(() => import('@/pages/admin/AdminQuizSections'));
const AdminMarkingTypes = lazy(() => import('@/pages/admin/AdminMarkingTypes'));
const AdminTestimonials = lazy(() => import('@/pages/admin/AdminTestimonials'));
const AdminAuditorium = lazy(() => import('@/pages/admin/AdminAuditorium'));
const AdminVideoQuestions = lazy(() => import('@/pages/admin/AdminVideoQuestions'));
const AdminWhatsApp = lazy(() => import('./pages/admin/AdminWhatsApp.tsx'));
const AdminExtensions = lazy(() => import('@/pages/admin/AdminExtensions'));
const AdminEventRegistrations = lazy(() => import('@/pages/admin/AdminEventRegistrations'));

import { useAuthStore } from '@/store/authStore';
import ContentProtection from '@/components/ContentProtection';
import { useSingleDeviceSession } from '@/hooks/useSingleDeviceSession';

const queryClient = new QueryClient();

function SessionGuard() {
  useSingleDeviceSession();
  return null;
}

const App = () => {
  const initialize = useAuthStore((state) => state.initialize);

  useEffect(() => {
    initialize();
  }, [initialize]);

  return (
  <QueryClientProvider client={queryClient}>
    <Toaster />
    <BrowserRouter
      future={{
        v7_startTransition: true,
        v7_relativeSplatPath: true,
      }}
    >
      <SessionGuard />
      <ContentProtection />
      <Suspense fallback={<div className="flex items-center justify-center min-h-screen font-serif text-ink">Loading...</div>}>
        <Routes>
          <Route path="/" element={<Home />} />
          <Route path="/faculty" element={<Faculty />} />
          <Route path="/gallery" element={<Gallery />} />
          <Route path="/faq" element={<FAQ />} />
          <Route path="/contact" element={<Contact />} />
          <Route path="/awards" element={<Awards />} />
          <Route path="/publications" element={<Publications />} />
          <Route path="/courses" element={<Membership />} />
          <Route path="/membership" element={<ProfessionalMembership />} />
          <Route path="/login" element={<Login />} />
          <Route path="/admin/login" element={<AdminLoginPage />} />
          <Route path="/register/batch-15" element={<RegistrationFeePage batchSlug="batch-15" />} />
          <Route path="/register/ccm-practical-series" element={<RegistrationFeePage batchSlug="ccm-2" />} />
          <Route path="/register/batch-10-edic-1" element={<RegistrationFeePage batchSlug="batch-10-edic-1" />} />
          <Route path="/register/edic-10" element={<RegistrationFeePage batchSlug="edic-10" />} />
          <Route path="/register/comprehensive-course-1" element={<RegistrationFeePage batchSlug="comprehensive-course-1" />} />
          <Route path="/register/comprehensive-1" element={<RegistrationFeePage batchSlug="comprehensive-1" />} />
          <Route path="/register/comprehensive-course-2" element={<RegistrationFeePage batchSlug="comprehensive-course-2" />} />
          <Route path="/register/comprehensive-2" element={<RegistrationFeePage batchSlug="comprehensive-2" />} />
          <Route path="/register/:batchSlug" element={<RegistrationFeePage />} />
          <Route path="/register" element={<Register />} />
          <Route path="/forgot-password" element={<ForgotPassword />} />
          <Route path="/reset-password" element={<ResetPassword />} />
          <Route path="/thank-you" element={<ThankYou />} />
          <Route path={`/events/${EVENT_SLUG}/register`} element={<EventConclaveRegister />} />
          <Route path={`/events/${EVENT_SLUG}/thank-you`} element={<EventConclaveThankYou />} />
          <Route
            path={`/events/${EVENT_SLUG_LEGACY}/register`}
            element={<Navigate to={`/events/${EVENT_SLUG}/register`} replace />}
          />
          <Route
            path={`/events/${EVENT_SLUG_LEGACY}/thank-you`}
            element={<Navigate to={`/events/${EVENT_SLUG}/thank-you`} replace />}
          />
          <Route path="/dashboard" element={<ProtectedRoute><StudentLayout /></ProtectedRoute>}>
            <Route index element={<Dashboard />} />
            <Route path="videos" element={<Videos />} />
            <Route path="videos/:id" element={<VideoDetail />} />
            <Route path="quiz" element={<Quiz />} />
            <Route path="quiz/:id/exam" element={<QuizExam />} />
            <Route path="quiz/:id/result" element={<QuizResult />} />
            <Route path="profile" element={<Profile />} />
            <Route path="payments" element={<Payments />} />
            <Route path="extend-subscription" element={<ExtendSubscription />} />
            <Route path="certificate" element={<Certificate />} />
          </Route>
          <Route path="/admin" element={<AdminRoute><AdminLayout /></AdminRoute>}>
            <Route index element={<AdminDashboard />} />
            <Route path="users" element={<AdminUsers />} />
            <Route path="users/:id" element={<AdminUserDetail />} />
            <Route path="payments" element={<AdminPayments />} />
            <Route path="packages" element={<AdminPackages />} />
            <Route path="extensions" element={<AdminExtensions />} />
            <Route path="events" element={<AdminEventRegistrations />} />
            <Route path="content/videos" element={<AdminVideos />} />
            <Route path="content/folders" element={<AdminFolders />} />
            <Route path="content/batches" element={<AdminBatches />} />
            <Route path="content/video-questions" element={<AdminVideoQuestions />} />
            <Route path="quiz/exams" element={<AdminExams />} />
            <Route path="quiz/questions" element={<AdminQuestions />} />
            <Route path="quiz/sections" element={<AdminQuizSections />} />
            <Route path="quiz/marking-types" element={<AdminMarkingTypes />} />
            <Route path="quiz/results" element={<AdminResults />} />
            <Route path="coupons" element={<AdminCoupons />} />
            <Route path="testimonials" element={<AdminTestimonials />} />
            <Route path="auditorium" element={<AdminAuditorium />} />
            <Route path="settings" element={<AdminSettings />} />
            <Route path="login-activity" element={<AdminLoginActivity />} />
            <Route path="communication/whatsapp" element={<AdminWhatsApp />} />
          </Route>
          <Route path="*" element={<NotFound />} />
        </Routes>
      </Suspense>
    </BrowserRouter>
  </QueryClientProvider>
  );
};

export default App;
