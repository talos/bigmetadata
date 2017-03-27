from flask import Flask, request
app = Flask(__name__)

#require 'sinatra'
#require 'json'
#require 'digest/sha2'
#
#class TravisWebhook < Sinatra::Base
#  set :token, ENV['TRAVIS_USER_TOKEN']
#
#  post '/' do
#    if not valid_request?
#      puts "Invalid payload request for repository #{repo_slug}"
#    else
#      payload = JSON.parse(params[:payload])
#      puts "Received valid payload for repository #{repo_slug}"
#    end
#  end

TOKEN = os.environ['TRAVIS_USER_TOKEN']


@app.route("/", methods=['POST'])
def receive():
    repo_slug = request.headers['Travis-Repo-Slug']
    auhorization = request.headers['Authorization']
    if valid_request(authorization, repo_slug)
        return "Received valid payload for {}".format(repo_slug)
    else:
        return "Invalid payload request for {}".format(repo_slug)


def valid_request(authorization, repo_slug):
    return authorization == hashlib.sha1(repo_slug + TOKEN).hexdigest()

#
#  def valid_request?
#    digest = Digest::SHA2.new.update("#{repo_slug}#{settings.token}")
#    digest.to_s == authorization
#  end
#
#  def authorization
#    env['HTTP_AUTHORIZATION']
#  end
#
#  def repo_slug
#    env['HTTP_TRAVIS_REPO_SLUG']
#  end
#end

if __name__ == "__main__":
    app.run()

