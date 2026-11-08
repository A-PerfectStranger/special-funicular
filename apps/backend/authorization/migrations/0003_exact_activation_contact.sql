
CREATE OR REPLACE FUNCTION public.e2_redeem(login_id uuid, token_hash text, issuer text, subject text,
  verified_contact text, authenticated_at timestamptz) RETURNS void
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $$
DECLARE inv public.identity_invitation; e public.school_roster_enrollment; aid uuid:=gen_random_uuid();
  stamp timestamptz:=clock_timestamp();
BEGIN
  -- Serialize against invitation replacement. Only this preloaded parent is associated.
  SELECT en.* INTO e FROM public.school_roster_enrollment en JOIN public.identity_invitation i
    ON i.parent_id=en.parent_id WHERE i.token_hash=e2_redeem.token_hash FOR UPDATE OF en;
  IF NOT FOUND THEN RAISE EXCEPTION 'activation denied' USING ERRCODE='28000'; END IF;
  SELECT * INTO inv FROM public.identity_invitation i WHERE i.token_hash=e2_redeem.token_hash FOR UPDATE;
  stamp:=clock_timestamp();
  IF inv.used_at IS NOT NULL OR inv.revoked_at IS NOT NULL OR inv.expires_at<=stamp
    OR verified_contact IS NULL OR e.contact<>verified_contact
    OR issuer IS NULL OR subject IS NULL OR length(subject) NOT BETWEEN 1 AND 255
    OR authenticated_at NOT BETWEEN stamp-interval '5 minutes' AND stamp+interval '30 seconds'
    OR NOT EXISTS(SELECT 1 FROM public.identity_loginrequest WHERE id=login_id
      AND purpose='activate' AND channel='mobile' AND consumed_at IS NOT NULL AND expires_at>stamp)
    OR NOT EXISTS(SELECT 1 FROM public.school_roster_school WHERE id=e.school_id AND active)
    OR EXISTS(SELECT 1 FROM public.school_roster_parent WHERE id=e.parent_id AND account_id IS NOT NULL)
    OR EXISTS(SELECT 1 FROM public.identity_account a WHERE a.issuer=e2_redeem.issuer AND a.subject=e2_redeem.subject) THEN
    RAISE EXCEPTION 'activation denied' USING ERRCODE='28000'; END IF;
  INSERT INTO public.identity_account(id,issuer,subject,role,active,version)
    VALUES(aid,issuer,subject,'PADRE',true,1);
  UPDATE public.school_roster_parent SET account_id=aid WHERE id=e.parent_id;
  UPDATE public.identity_invitation SET used_at=stamp WHERE id=inv.id;
  PERFORM public.e1_append('PARENT_ACTIVATED',aid,e.school_id,inv.id,
    jsonb_build_object('parent_id',e.parent_id,'result','ASSOCIATED'));
END $$;


ALTER FUNCTION public.e2_redeem(uuid,text,text,text,text,timestamptz) OWNER TO retiro_evidence_writer;
REVOKE ALL ON FUNCTION public.e2_redeem(uuid,text,text,text,text,timestamptz) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.e2_redeem(uuid,text,text,text,text,timestamptz) TO retiro_runtime;
