from django.shortcuts import render, redirect
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt
from django.contrib import messages
from onlinetest.models import Question, Answer, Profile, Config
from onlinetest.forms import ProfileForm, AnswerForm
from django.http import HttpResponse, HttpResponseRedirect
from django.contrib.auth import logout
from django.utils import timezone
import os
import csv

def index(req):
    config = Config.objects.all().first()
    if req.user.is_authenticated:
        curr_time = timezone.now()
        if curr_time < config.start_time and not req.user.is_staff:
            logout_user(req)
            return HttpResponse('Second wave of First round of auditions will go live at 9.00 PM on 4th November 2019.')
        if curr_time > config.end_time and not req.user.is_staff:
            logout_user(req)
            return HttpResponse('First round of GLUG auditions has finished. See you next year :)')
        return redirect('/rules/')
    return render(req, 'onlinetest/index.html')

@login_required
def logout_user(req):
    logout(req)
    return redirect('/')

@login_required
def questions(req):
    profile = Profile.objects.get(user=req.user)
    if profile.time_left <= 0:
        return HttpResponseRedirect('/finish/', {})
    questions = Question.objects.all()
    answers = Answer.objects.filter(user=req.user)
    # pair up the questions with their corresponding answers
    for question in questions:
        is_answered = answers.filter(question=question).exists()
        if is_answered:
            question.answer = answers.filter(question=question).first().text
        else:
            question.answer = None

    time_left = profile.time_left
    ctx = { 'questions': questions, 'user': req.user , 'time_left': time_left}
    return render(req, 'onlinetest/questions.html', ctx)

@login_required
def answers(req, qid):
    if req.method == 'POST':
        form = AnswerForm(req.POST)
        if form.is_valid:
            question = Question.objects.get(id=qid)
            user = User.objects.get(id=req.user.id)
            already_submitted = Answer.objects.filter(question=question, user=user).exists()
            if already_submitted:
                answer = Answer.objects.filter(question=question, user=user).first()
                answer.text = req.POST['text']
                answer.save()
                messages.info(req, 'Your answer for question {} has been updated.'.format(qid - 6))
            else:
                answer = Answer(question=question, user=user, text=req.POST['text'])
                answer.save()
                messages.info(req, 'Answer submitted successfully for question {}.'.format(qid - 6))
            return redirect('/questions/#q{}'.format(qid+1))
        else:
            messages.info(req, 'Please supply a valid answer.')
            return redirect('/questions/#q{}'.format(qid))
    else:
        return HttpResponse(status=404)

@login_required
def rules(req):
    if req.method == 'POST':
        form = ProfileForm(req.POST)
        if form.is_valid:
            full_name = req.POST['full_name']
            phone = req.POST['phone']
            rollno = req.POST['rollno']
            user = User.objects.get(id=req.user.id)
            profile = Profile(user=user, full_name=full_name, phone=phone, rollno=rollno)
            profile.save()
            return redirect('/questions/')
    else:
        if Profile.objects.filter(user=req.user).exists():
            return HttpResponseRedirect('/questions/',{})   
        ctx = {'user': req.user, 'noprofile': True}
        return render(req, 'onlinetest/rules.html', ctx)

@login_required
@csrf_exempt
def UpdateTime(req):
    if req.method == "POST":
        print(req.POST)
        t_left = int(req.POST['time_left'])
        profile = Profile.objects.get(user=req.user)
        if t_left <= 0:
            profile.time_left = 0
            profile.save()
            return HttpResponse(status=200)

        if t_left < profile.time_left:
            # possibly valid
            profile.time_left = t_left
            profile.save()
            return HttpResponse(status=200)

        else:
            return HttpResponse(status=406) # 406-NotAcceptable
    else:
        return None

@login_required
def finish(req):
    ctx = { 'user': req.user }
    return render(req, 'onlinetest/finish.html', ctx)

@login_required
def results(req):
    if req.user.is_staff:
        # allow access to only staff for now
        profiles = Profile.objects.filter(selected=True)
        ctx = {'profiles': profiles, 'count': len(profiles)}
        return render(req, 'onlinetest/results.html', ctx)
    else:
        return HttpResponse('You are not allowed to access the results.')


def scrape_answers(full_name, user_id):
    answers = Answer.objects.filter(user=user_id)
    f = open(os.path.join(os.environ['HOME'], 'results.txt'), 'a')
    f.write('################################\n')
    f.write(full_name + "\n")
    f.write('---------------------------------\n')

    for answer in answers:
        f.write(answer.text)
        f.write('\n\n')

@login_required
def print_results(req):
    if req.user.is_staff:
        profiles = Profile.objects.filter(selected=True)
        for profile in profiles:
            scrape_answers(profile.full_name, profile.user)
        return HttpResponse('Done Saving Results.')
    else:
        return HttpResponse('You are not allowed to access the results.')


def export_profile_csv(req):
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="profiles.csv"'

    writer = csv.writer(response)
    writer.writerow(['Name', 'Email address', 'Phone','RollNo'])

    profiles = Profile.objects.all()
    for profile in profiles:
        writer.writerow([profile.full_name, profile.user.email, profile.phone, profile.rollno])

    return response
