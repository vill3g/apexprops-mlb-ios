
file_path = r'C:\Users\Vill3\Desktop\kalshi-ai-trader\backend\btc\ml_engine.py'
with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

replacements = [
    (
        '''        except Exception as e:\n            logger.warning(f"[MLEngine] Calibration fit failed, using raw probabilities: {e}")\n            self.calibrator = None''',
        '''        except (ValueError, TypeError) as e:\n            logger.warning(f"[MLEngine] Calibration fit failed, using raw probabilities: {e}")\n            self.calibrator = None'''
    ),
    (
        '''        except (ValueError, KeyError, AttributeError):\n            # Fallback if class 1 wasn't in the training data\n            return np.array([0.0] * X.shape[0])''',
        '''        except (ValueError, KeyError, AttributeError) as e:\n            logger.warning(f"[MLEngine] predict_proba failed: {e}")\n            # Fallback if class 1 wasn't in the training data\n            return np.array([0.0] * X.shape[0])'''
    ),
    (
        '''        except Exception as e:\n            logger.warning(f"[MLEngine] Calibrated prediction failed: {e}")\n            return raw''',
        '''        except (ValueError, TypeError) as e:\n            logger.warning(f"[MLEngine] Calibrated prediction failed: {e}")\n            return raw'''
    ),
    (
        '''    except Exception:\n        is_wknd, hr_day = 0.0, 12.0''',
        '''    except (ValueError, TypeError, OSError) as e:\n        logger.warning(f"[MLEngine] datetime parse error: {e}")\n        is_wknd, hr_day = 0.0, 12.0'''
    ),
    (
        '''    except Exception:\n        vol_15m_ratio = 1.0''',
        '''    except (ValueError, TypeError, KeyError) as e:\n        logger.warning(f"[MLEngine] volume calculation error: {e}")\n        vol_15m_ratio = 1.0'''
    ),
    (
        '''    except Exception:\n        vol_regime = 0.5''',
        '''    except (ValueError, TypeError, KeyError) as e:\n        logger.warning(f"[MLEngine] atr regime calculation error: {e}")\n        vol_regime = 0.5'''
    ),
    (
        '''                except Exception:\n                    pass''',
        '''                except (ValueError, TypeError, KeyError, IndexError) as e:\n                    logger.warning(f"[MLEngine] feature extraction error: {e}")'''
    ),
    (
        '''        except Exception as e:\n            logger.error(f"[MLEngine] Failed to extract reasoning: {e}")\n            return prob, "ML Reasoning unavailable."''',
        '''        except (ValueError, TypeError, KeyError, AttributeError) as e:\n            logger.error(f"[MLEngine] Failed to extract reasoning: {e}")\n            return prob, "ML Reasoning unavailable."'''
    ),
    (
        '''        except Exception as e:\n            logger.error(f"[MLEngine] Error loading trades: {e}")\n            return None, None, None''',
        '''        except (json.JSONDecodeError, FileNotFoundError, OSError) as e:\n            logger.error(f"[MLEngine] Error loading trades: {e}")\n            return None, None, None'''
    ),
    (
        '''                except Exception as e:\n                    logger.warning(f"[ML] Training background worker error: {e}")''',
        '''                except (ValueError, TypeError) as e:\n                    logger.warning(f"[ML] Training background worker error: {e}")'''
    ),
    (
        '''            except Exception as e:\n                logger.debug(f"[MLEngine] Could not read mtime for {self.history_file}: {e}")\n                mtime = 0.0''',
        '''            except OSError as e:\n                logger.warning(f"[MLEngine] Could not read mtime for {self.history_file}: {e}")\n                mtime = 0.0'''
    ),
    (
        '''                except Exception as e:\n                    logger.warning(f"[MLEngine] Failed to load cache: {e}")''',
        '''                except (FileNotFoundError, OSError, ValueError, TypeError) as e:\n                    logger.warning(f"[MLEngine] Failed to load cache: {e}")'''
    ),
    (
        '''                        except Exception as e:\n                            logger.warning(f"[MLEngine] Failed to load cache fallback: {e}")''',
        '''                        except (FileNotFoundError, OSError, ValueError, TypeError) as e:\n                            logger.warning(f"[MLEngine] Failed to load cache fallback: {e}")'''
    ),
    (
        '''                        except Exception as e:\n                            logger.warning(f"[MLEngine] Failed to cache model to disk: {e}")''',
        '''                        except (FileNotFoundError, OSError) as e:\n                            logger.warning(f"[MLEngine] Failed to cache model to disk: {e}")'''
    ),
    (
        '''            except Exception as e:\n                logger.error(f"[MLEngine] Training failed: {e}", exc_info=True)\n            return 0''',
        '''            except (ValueError, TypeError, KeyError, RuntimeError) as e:\n                logger.error(f"[MLEngine] Training failed: {e}", exc_info=True)\n            return 0'''
    ),
    (
        '''            except Exception as e:\n                logger.warning(f"[MLEngine] Failed to load robust cache fallback: {e}")''',
        '''            except (FileNotFoundError, OSError, ValueError, TypeError) as e:\n                logger.warning(f"[MLEngine] Failed to load robust cache fallback: {e}")'''
    ),
    (
        '''                except Exception as e:\n                    logger.debug(f"[ML] datetime parse error: {e}")''',
        '''                except (ValueError, TypeError) as e:\n                    logger.warning(f"[ML] datetime parse error: {e}")'''
    ),
    (
        '''                except Exception:\n                    ny_dt = datetime.now(ZoneInfo("America/New_York"))''',
        '''                except (ValueError, TypeError) as e:\n                    logger.warning(f"[MLEngine] fallback datetime parse error: {e}")\n                    ny_dt = datetime.now(ZoneInfo("America/New_York"))'''
    ),
    (
        '''                except Exception as e:\n                    logger.warning(f"[MLEngine] Failed to cache historical model to disk: {e}")''',
        '''                except (FileNotFoundError, OSError) as e:\n                    logger.warning(f"[MLEngine] Failed to cache historical model to disk: {e}")'''
    )
]

modified_content = content
for target, repl in replacements:
    if target in modified_content:
        modified_content = modified_content.replace(target, repl)
    else:
        print(f"Target not found: {target[:40]}")

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(modified_content)

print('Success')
