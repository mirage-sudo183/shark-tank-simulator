// Firebase configuration for Shark Tank Simulator
// Configuration is loaded from firebase-env.js (gitignored)

import { initializeApp } from 'https://www.gstatic.com/firebasejs/10.7.1/firebase-app.js';
import {
  getAuth,
  signInWithPopup,
  signOut,
  TwitterAuthProvider,
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

// Twitter Auth Provider
const twitterProvider = new TwitterAuthProvider();

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
    const twitterData = user.providerData.find(p => p.providerId === 'twitter.com');
    const twitterHandle = twitterData?.displayName || user.displayName || 'unknown';

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
 * @param {string} type - 'verified' or 'unverified'
 * @param {number} limitCount - Max entries to return
 */
async function getLeaderboard(type = 'verified', limitCount = 50) {
  let q;

  if (type === 'verified') {
    q = query(
      collection(db, 'pitches'),
      where('outcome.result', '==', 'deal'),
      where('verification.type', '!=', 'unverified'),
      orderBy('outcome.dealAmount', 'desc'),
      limit(limitCount)
    );
  } else {
    q = query(
      collection(db, 'pitches'),
      where('outcome.result', '==', 'deal'),
      orderBy('outcome.dealAmount', 'desc'),
      limit(limitCount)
    );
  }

  const snapshot = await getDocs(q);
  return snapshot.docs.map((doc, index) => ({
    rank: index + 1,
    ...doc.data()
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
  signOutUser,
  getIdToken,
  onAuthChange,
  getCurrentUser,
  savePitchResult,
  getLeaderboard,
  getUserBestPitch
};
