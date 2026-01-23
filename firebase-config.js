// Firebase configuration for Shark Tank Simulator
// Configuration is loaded from firebase-env.js (gitignored)

import { initializeApp } from 'https://www.gstatic.com/firebasejs/10.7.1/firebase-app.js';
import {
  getAuth,
  signInWithPopup,
  signOut,
  TwitterAuthProvider,
  GoogleAuthProvider,
  createUserWithEmailAndPassword,
  signInWithEmailAndPassword,
  sendSignInLinkToEmail,
  isSignInWithEmailLink,
  signInWithEmailLink,
  updateProfile,
  onAuthStateChanged
} from 'https://www.gstatic.com/firebasejs/10.7.1/firebase-auth.js';
import {
  getFirestore,
  doc,
  getDoc,
  setDoc,
  updateDoc,
  collection,
  query,
  where,
  orderBy,
  limit,
  getDocs,
  serverTimestamp
} from 'https://www.gstatic.com/firebasejs/10.7.1/firebase-firestore.js';

// Firebase configuration loaded from firebase-env.js
// This file must be loaded before firebase-config.js in index.html
const firebaseConfig = window.FIREBASE_CONFIG;

if (!firebaseConfig || !firebaseConfig.apiKey || firebaseConfig.apiKey === 'YOUR_FIREBASE_API_KEY') {
  console.error('Firebase configuration not found or incomplete!');
  console.error('Please copy firebase-env.example.js to firebase-env.js and add your API key.');
}

// Initialize Firebase
const app = initializeApp(firebaseConfig);
const auth = getAuth(app);
const db = getFirestore(app);

// Auth Providers
const twitterProvider = new TwitterAuthProvider();
const googleProvider = new GoogleAuthProvider();

// Current user state
let currentUser = null;

/**
 * Sign in with Twitter/X
 * @returns {Promise<{user: object, twitterHandle: string}>}
 */
async function signInWithTwitter() {
  try {
    const result = await signInWithPopup(auth, twitterProvider);
    const user = result.user;

    // Get Twitter handle from provider data
    // Twitter stores username in 'uid' field of providerData (e.g., "12345678")
    // and screen name can be extracted from the credential or reloadUserInfo
    const twitterData = user.providerData.find(p => p.providerId === 'twitter.com');

    // Try to get the actual Twitter username (screen_name)
    // Firebase stores it in reloadUserInfo.screenName after auth
    let twitterHandle = 'unknown';
    const additionalInfo = result._tokenResponse;

    if (additionalInfo && additionalInfo.screenName) {
      twitterHandle = additionalInfo.screenName;
    } else if (additionalInfo && additionalInfo.displayName) {
      // Some versions use displayName in tokenResponse
      twitterHandle = additionalInfo.displayName;
    } else if (twitterData?.uid) {
      // The uid in providerData is actually the Twitter username for Twitter provider
      twitterHandle = twitterData.uid;
    } else {
      twitterHandle = user.displayName || 'unknown';
    }

    // Get Twitter user ID from the credential
    const credential = TwitterAuthProvider.credentialFromResult(result);

    // Create or update user document in Firestore
    const userRef = doc(db, 'users', user.uid);
    const userDoc = await getDoc(userRef);

    const userData = {
      email: user.email,
      displayName: user.displayName,
      photoURL: user.photoURL,
      twitterHandle: twitterHandle,
      provider: 'twitter',
      lastLoginAt: serverTimestamp()
    };

    if (!userDoc.exists()) {
      // New user
      userData.createdAt = serverTimestamp();
      userData.pitchesThisWeek = 0;
      userData.verifications = {};
      await setDoc(userRef, userData);
    } else {
      // Existing user - update last login
      await updateDoc(userRef, userData);
    }

    currentUser = {
      uid: user.uid,
      ...userData,
      twitterHandle: twitterHandle
    };

    return { user: currentUser, twitterHandle };
  } catch (error) {
    console.error('Twitter sign-in error:', error);
    throw error;
  }
}

/**
 * Sign in with Google
 * @returns {Promise<{user: object}>}
 */
async function signInWithGoogle() {
  try {
    const result = await signInWithPopup(auth, googleProvider);
    const user = result.user;

    // Create or update user document in Firestore
    const userRef = doc(db, 'users', user.uid);
    const userDoc = await getDoc(userRef);

    const userData = {
      email: user.email,
      displayName: user.displayName,
      photoURL: user.photoURL,
      provider: 'google',
      lastLoginAt: serverTimestamp()
    };

    if (!userDoc.exists()) {
      // New user
      userData.createdAt = serverTimestamp();
      userData.pitchesThisWeek = 0;
      userData.verifications = {};
      await setDoc(userRef, userData);
    } else {
      // Existing user - update last login
      await updateDoc(userRef, userData);
    }

    currentUser = {
      uid: user.uid,
      ...userData
    };

    return { user: currentUser };
  } catch (error) {
    console.error('Google sign-in error:', error);
    throw error;
  }
}

/**
 * Register with email and password
 * @param {string} email
 * @param {string} password
 * @param {string} displayName
 * @returns {Promise<{user: object}>}
 */
async function registerWithEmail(email, password, displayName) {
  try {
    const result = await createUserWithEmailAndPassword(auth, email, password);
    const user = result.user;

    // Update profile with display name
    await updateProfile(user, { displayName });

    // Create user document in Firestore
    const userRef = doc(db, 'users', user.uid);
    const userData = {
      email: user.email,
      displayName: displayName,
      photoURL: null,
      provider: 'email',
      createdAt: serverTimestamp(),
      lastLoginAt: serverTimestamp(),
      pitchesThisWeek: 0,
      verifications: {}
    };

    await setDoc(userRef, userData);

    currentUser = {
      uid: user.uid,
      ...userData
    };

    return { user: currentUser };
  } catch (error) {
    console.error('Email registration error:', error);
    throw error;
  }
}

/**
 * Sign in with email and password
 * @param {string} email
 * @param {string} password
 * @returns {Promise<{user: object}>}
 */
async function signInWithEmail(email, password) {
  try {
    const result = await signInWithEmailAndPassword(auth, email, password);
    const user = result.user;

    // Get or create user document in Firestore
    const userRef = doc(db, 'users', user.uid);
    const userDoc = await getDoc(userRef);

    const userData = {
      email: user.email,
      displayName: user.displayName || email.split('@')[0],
      photoURL: user.photoURL,
      provider: 'email',
      lastLoginAt: serverTimestamp()
    };

    if (!userDoc.exists()) {
      userData.createdAt = serverTimestamp();
      userData.pitchesThisWeek = 0;
      userData.verifications = {};
      await setDoc(userRef, userData);
    } else {
      await updateDoc(userRef, userData);
    }

    currentUser = {
      uid: user.uid,
      ...userData
    };

    return { user: currentUser };
  } catch (error) {
    console.error('Email sign-in error:', error);
    throw error;
  }
}

/**
 * Send magic link email for passwordless sign-in
 * @param {string} email
 * @returns {Promise<void>}
 */
async function sendMagicLink(email) {
  const actionCodeSettings = {
    url: window.location.origin + window.location.pathname,
    handleCodeInApp: true
  };

  try {
    await sendSignInLinkToEmail(auth, email, actionCodeSettings);
    // Save the email locally to complete sign-in when user returns
    window.localStorage.setItem('emailForSignIn', email);
  } catch (error) {
    console.error('Magic link error:', error);
    throw error;
  }
}

/**
 * Complete magic link sign-in (called when user returns from email link)
 * @returns {Promise<{user: object}|null>}
 */
async function completeMagicLinkSignIn() {
  if (!isSignInWithEmailLink(auth, window.location.href)) {
    return null;
  }

  let email = window.localStorage.getItem('emailForSignIn');
  if (!email) {
    // User opened the link on a different device
    email = window.prompt('Please provide your email for confirmation');
  }

  if (!email) {
    throw new Error('Email is required to complete sign-in');
  }

  try {
    const result = await signInWithEmailLink(auth, email, window.location.href);
    const user = result.user;

    // Clear the email from storage
    window.localStorage.removeItem('emailForSignIn');

    // Clean up the URL
    window.history.replaceState(null, '', window.location.pathname);

    // Create or update user document in Firestore
    const userRef = doc(db, 'users', user.uid);
    const userDoc = await getDoc(userRef);

    const userData = {
      email: user.email,
      displayName: user.displayName || email.split('@')[0],
      photoURL: user.photoURL,
      provider: 'email_link',
      lastLoginAt: serverTimestamp()
    };

    if (!userDoc.exists()) {
      userData.createdAt = serverTimestamp();
      userData.pitchesThisWeek = 0;
      userData.verifications = {};
      await setDoc(userRef, userData);
    } else {
      await updateDoc(userRef, userData);
    }

    currentUser = {
      uid: user.uid,
      ...userData
    };

    return { user: currentUser };
  } catch (error) {
    console.error('Magic link sign-in error:', error);
    throw error;
  }
}

/**
 * Sign out the current user
 */
async function signOutUser() {
  try {
    await signOut(auth);
    currentUser = null;
  } catch (error) {
    console.error('Sign out error:', error);
    throw error;
  }
}

/**
 * Get the current user's Firebase ID token for API calls
 * @returns {Promise<string|null>}
 */
async function getIdToken() {
  const user = auth.currentUser;
  if (!user) return null;
  return await user.getIdToken();
}

/**
 * Listen for auth state changes
 * @param {Function} callback - Called with (user, twitterHandle) or (null, null)
 */
function onAuthChange(callback) {
  onAuthStateChanged(auth, async (user) => {
    if (user) {
      // Get user data from Firestore
      const userRef = doc(db, 'users', user.uid);
      const userDoc = await getDoc(userRef);

      if (userDoc.exists()) {
        const userData = userDoc.data();
        currentUser = {
          uid: user.uid,
          ...userData
        };
        callback(currentUser, userData.twitterHandle);
      } else {
        // User exists in auth but not Firestore - shouldn't happen normally
        const twitterData = user.providerData.find(p => p.providerId === 'twitter.com');
        callback({ uid: user.uid, displayName: user.displayName }, twitterData?.displayName || user.displayName);
      }
    } else {
      currentUser = null;
      callback(null, null);
    }
  });
}

/**
 * Get current user
 * @returns {object|null}
 */
function getCurrentUser() {
  return currentUser;
}

// ============ Leaderboard Functions ============

/**
 * Save a pitch result to Firestore
 * @param {object} pitchData - The pitch data
 * @param {object} outcome - Deal outcome
 * @param {object} verification - Verification info
 */
async function savePitchResult(pitchData, outcome, verification = { type: 'unverified' }) {
  if (!currentUser) throw new Error('Not authenticated');

  const pitchRef = doc(collection(db, 'pitches'));
  await setDoc(pitchRef, {
    id: pitchRef.id,
    userId: currentUser.uid,
    userTwitterHandle: currentUser.twitterHandle,
    userDisplayName: currentUser.displayName,
    pitchData: pitchData,
    outcome: outcome,
    verification: verification,
    createdAt: serverTimestamp()
  });

  return pitchRef.id;
}

/**
 * Get leaderboard entries
 * @param {string} type - 'verified', 'all', or 'weekly'
 * @param {number} limitCount - Max entries to return
 */
async function getLeaderboard(type = 'verified', limitCount = 50) {
  // Fetch all deals, then filter and sort client-side
  // This avoids needing composite indexes in Firestore
  const q = query(
    collection(db, 'pitches'),
    where('outcome.result', '==', 'deal')
  );

  const snapshot = await getDocs(q);
  let results = snapshot.docs.map(doc => doc.data());

  // Filter by verification type if needed
  if (type === 'verified') {
    results = results.filter(p => p.verification?.type !== 'unverified');
  }

  // Filter by week if weekly type
  if (type === 'weekly') {
    // Calculate start of current week (Monday 00:00 UTC)
    const now = new Date();
    const dayOfWeek = now.getUTCDay();
    const daysToMonday = dayOfWeek === 0 ? 6 : dayOfWeek - 1;
    const startOfWeek = new Date(now);
    startOfWeek.setUTCDate(now.getUTCDate() - daysToMonday);
    startOfWeek.setUTCHours(0, 0, 0, 0);
    const weekStartMs = startOfWeek.getTime();

    results = results.filter(p => {
      const createdAt = p.createdAt;
      let timestampMs = 0;
      if (createdAt?.toMillis) {
        // Firestore Timestamp
        timestampMs = createdAt.toMillis();
      } else if (createdAt?.seconds) {
        // Firestore Timestamp object
        timestampMs = createdAt.seconds * 1000;
      } else if (typeof createdAt === 'number') {
        timestampMs = createdAt;
      }
      return timestampMs >= weekStartMs;
    });
  }

  // Sort by deal amount descending
  results.sort((a, b) => (b.outcome?.dealAmount || 0) - (a.outcome?.dealAmount || 0));

  // Limit and add rank
  return results.slice(0, limitCount).map((data, index) => ({
    rank: index + 1,
    ...data
  }));
}

/**
 * Get user's best pitch
 * @param {string} userId
 */
async function getUserBestPitch(userId) {
  const q = query(
    collection(db, 'pitches'),
    where('userId', '==', userId),
    where('outcome.result', '==', 'deal'),
    orderBy('outcome.dealAmount', 'desc'),
    limit(1)
  );

  const snapshot = await getDocs(q);
  if (snapshot.empty) return null;
  return snapshot.docs[0].data();
}

// Export for use in app.js
export {
  auth,
  db,
  signInWithTwitter,
  signInWithGoogle,
  registerWithEmail,
  signInWithEmail,
  sendMagicLink,
  completeMagicLinkSignIn,
  signOutUser,
  getIdToken,
  onAuthChange,
  getCurrentUser,
  savePitchResult,
  getLeaderboard,
  getUserBestPitch
};
